"""429 handling (#9) and the render output lock (#10)."""
import json
import os

import pytest
import typer
from typer.testing import CliRunner

from walkthrough.__main__ import _claim_output, _pid_alive, app
from walkthrough.narrator.base import ProviderError, RateLimited, check_response
from walkthrough.narrator.fake import FakeNarrator

from conftest import commit_file
from test_validate import AFTER, filled_plan


class Resp:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.is_success = 200 <= status_code < 300


def test_check_response_passes_success():
    check_response(Resp())  # no raise


def test_429_raises_rate_limited_with_retry_after():
    with pytest.raises(RateLimited) as e:
        check_response(Resp(429, text="too many concurrent requests",
                            headers={"retry-after": "7"}))
    assert e.value.retry_after == 7.0
    # The reason lives in the body, not the status line.
    assert "too many concurrent requests" in str(e.value)


def test_429_without_retry_after_leaves_backoff_to_caller():
    with pytest.raises(RateLimited) as e:
        check_response(Resp(429, text="slow down"))
    assert e.value.retry_after is None


def test_http_date_retry_after_is_ignored_rather_than_crashing():
    with pytest.raises(RateLimited) as e:
        check_response(Resp(429, headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}))
    assert e.value.retry_after is None


def test_other_errors_carry_the_api_message():
    with pytest.raises(ProviderError) as e:
        check_response(Resp(401, text='{"detail":"invalid api key"}'))
    assert "401" in str(e.value) and "invalid api key" in str(e.value)


def test_long_error_bodies_are_truncated():
    with pytest.raises(ProviderError) as e:
        check_response(Resp(500, text="x" * 5000))
    assert len(str(e.value)) < 400


def test_rate_limited_is_a_provider_error():
    # narrate's generic `except Exception` must not shadow the 429 branch.
    assert issubclass(RateLimited, ProviderError)


# --- render output lock (#10) ---

def test_claim_output_creates_lock_holding_our_pid(tmp_path):
    final = tmp_path / "out.mp4"
    lock = _claim_output(final)
    assert lock.exists() and lock.read_text().strip() == str(os.getpid())


def test_second_render_refuses_while_a_live_pid_holds_the_lock(tmp_path):
    final = tmp_path / "out.mp4"
    lock = final.with_name("out.mp4.lock")
    lock.write_text("1")  # pid 1 is always alive
    with pytest.raises(typer.Exit) as e:
        _claim_output(final)
    assert e.value.exit_code == 4
    assert lock.read_text() == "1"  # the live holder's lock is left alone


def test_stale_lock_is_taken_over(tmp_path, monkeypatch):
    final = tmp_path / "out.mp4"
    lock = final.with_name("out.mp4.lock")
    lock.write_text("424242")
    monkeypatch.setattr("walkthrough.__main__._pid_alive", lambda pid: False)
    _claim_output(final)
    assert lock.read_text().strip() == str(os.getpid())


def test_garbage_lock_is_taken_over(tmp_path):
    final = tmp_path / "out.mp4"
    lock = final.with_name("out.mp4.lock")
    lock.write_text("not-a-pid")
    _claim_output(final)
    assert lock.read_text().strip() == str(os.getpid())


def test_pid_alive_reports_this_process(tmp_path):
    assert _pid_alive(os.getpid()) is True
    assert _pid_alive(424242) is False


# --- the behavior the 429 fix exists for ---

def test_a_429_makes_the_run_go_serial_and_still_finish(repo, monkeypatch, tmp_path):
    """The failure we hit live: -j > 1 got 429'd and the chapter was abandoned.
    Now the run drops to one-at-a-time and every chapter still lands."""
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", AFTER)
    wt = filled_plan()
    wt.meta.base_sha, wt.meta.head_sha = base, head
    wtdir = repo / ".walkthrough"
    wtdir.mkdir()
    (wtdir / "walkthrough.json").write_text(wt.model_dump_json())
    monkeypatch.chdir(repo)
    monkeypatch.setenv("WALKTHROUGH_CACHE", str(tmp_path / "cache"))

    calls: list[str] = []

    class RateLimitingNarrator:
        provider, model, voice_id = "flaky", "m", "v"

        def synthesize(self, text, out, previous_text="", next_text=""):
            calls.append(text)
            if len(calls) == 1:  # first request of the run is rejected
                raise RateLimited("HTTP 429: too many concurrent requests",
                                  retry_after=0)
            return FakeNarrator().synthesize(text, out, previous_text, next_text)

    monkeypatch.setattr("walkthrough.__main__.get_narrator",
                        lambda: RateLimitingNarrator())
    result = CliRunner().invoke(app, ["narrate"])

    assert result.exit_code == 0, result.output
    assert "rate limited" in result.output
    saved = json.loads((wtdir / "walkthrough.json").read_text())
    assert all(ch["audio"]["duration_ms"] > 0 for ch in saved["chapters"])


def test_a_persistent_429_still_fails_with_the_api_message(repo, monkeypatch, tmp_path):
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", AFTER)
    wt = filled_plan()
    wt.meta.base_sha, wt.meta.head_sha = base, head
    wtdir = repo / ".walkthrough"
    wtdir.mkdir()
    (wtdir / "walkthrough.json").write_text(wt.model_dump_json())
    monkeypatch.chdir(repo)
    monkeypatch.setenv("WALKTHROUGH_CACHE", str(tmp_path / "cache"))

    class AlwaysLimited:
        provider, model, voice_id = "flaky", "m", "v"

        def synthesize(self, text, out, previous_text="", next_text=""):
            raise RateLimited("HTTP 429: quota exceeded", retry_after=0)

    monkeypatch.setattr("walkthrough.__main__.get_narrator", lambda: AlwaysLimited())
    result = CliRunner().invoke(app, ["narrate"])

    assert result.exit_code == 3  # provider error
    assert "quota exceeded" in result.output  # the reason, not just "429"
