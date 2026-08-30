import json
import subprocess
import wave
from pathlib import Path

import pytest

from walkthrough.narrator import cache
from walkthrough.narrator.base import RateLimited, get_narrator
from walkthrough.narrator.fake import FakeNarrator

from conftest import commit_file
from test_validate import AFTER, filled_plan


def test_cache_key_is_sha256_of_joined_fields_with_stitch_context():
    import hashlib
    expected = hashlib.sha256("fake:fake-1:v1:\x00hello\x00".encode()).hexdigest()
    assert cache.cache_key("fake", "fake-1", "v1", "hello") == expected
    with_ctx = cache.cache_key("fake", "fake-1", "v1", "hello",
                               previous_text="a", next_text="b")
    assert with_ctx != expected
    assert with_ctx == hashlib.sha256("fake:fake-1:v1:a\x00hello\x00b".encode()).hexdigest()


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("WALKTHROUGH_CACHE", str(tmp_path / "cache"))
    key = cache.cache_key("fake", "fake-1", "v1", "hi")
    assert cache.lookup(key) is None
    src = tmp_path / "clip.mp3"
    src.write_bytes(b"AUDIO")
    cache.store(key, src, 1234)
    clip = cache.lookup(key)
    assert clip is not None and clip.duration_ms == 1234
    assert clip.path.read_bytes() == b"AUDIO"


def test_fake_narrator_duration_scales_with_word_count(tmp_path):
    n = FakeNarrator()
    short = n.synthesize("one two three", tmp_path / "a.mp3")
    long = n.synthesize(" ".join(["word"] * 50), tmp_path / "b.mp3")
    assert long.duration_ms > short.duration_ms
    with wave.open(str(tmp_path / "a.mp3"), "rb") as w:  # valid audio container
        assert w.getnframes() > 0


def test_get_narrator_fake_needs_no_key(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "fake")
    monkeypatch.delenv("TTS_API_KEY", raising=False)
    assert get_narrator().provider == "fake"


def test_get_narrator_missing_key(monkeypatch):
    import pytest
    from walkthrough.narrator.base import MissingKeyError
    monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
    monkeypatch.delenv("TTS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(MissingKeyError):
        get_narrator()


def test_get_narrator_accepts_provider_specific_key(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
    monkeypatch.delenv("TTS_API_KEY", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    assert get_narrator().provider == "elevenlabs"


def test_narrate_end_to_end_fake_and_cache_hit(repo, monkeypatch):
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", AFTER)
    wt = filled_plan()
    wt.meta.base_sha, wt.meta.head_sha = base, head
    wtdir = repo / ".walkthrough"
    wtdir.mkdir()
    (wtdir / "walkthrough.json").write_text(wt.model_dump_json())

    env = {"TTS_PROVIDER": "fake", "WALKTHROUGH_CACHE": str(repo / "cache"),
           "PATH": __import__("os").environ["PATH"]}
    res = subprocess.run(["walkthrough", "narrate"], cwd=repo,
                         capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr
    saved = json.loads((wtdir / "walkthrough.json").read_text())
    assert saved["chapters"][0]["audio"]["path"] == "audio/c01.mp3"
    assert saved["chapters"][0]["audio"]["duration_ms"] > 0
    assert (wtdir / "audio" / "c02.mp3").exists()
    assert "3/3 clips, 0 cached" in res.stdout

    res2 = subprocess.run(["walkthrough", "narrate"], cwd=repo,
                          capture_output=True, text=True, env=env)
    assert "3/3 clips, 3 cached" in res2.stdout


def _repo_with_plan(repo: Path) -> Path:
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", AFTER)
    wt = filled_plan()
    wt.meta.base_sha, wt.meta.head_sha = base, head
    wtdir = repo / ".walkthrough"
    wtdir.mkdir()
    (wtdir / "walkthrough.json").write_text(wt.model_dump_json())
    return wtdir


def _clean_env(repo: Path) -> dict[str, str]:
    """No TTS_* inherited — the installed package is what dotenv would find."""
    import os
    return {"WALKTHROUGH_CACHE": str(repo / "cache"), "PATH": os.environ["PATH"]}


def test_narrate_reads_env_from_working_repo(repo):
    """The package lives in this checkout; the repo under review is elsewhere."""
    _repo_with_plan(repo)
    (repo / ".env").write_text("TTS_PROVIDER=fake\n")
    res = subprocess.run(["walkthrough", "narrate"], cwd=repo,
                         capture_output=True, text=True, env=_clean_env(repo))
    assert res.returncode == 0, res.stderr


def test_narrate_finds_env_at_repo_root_from_subdir(repo):
    _repo_with_plan(repo)
    (repo / ".env").write_text("TTS_PROVIDER=fake\n")
    sub = repo / "sub"
    sub.mkdir()
    res = subprocess.run(["walkthrough", "narrate"], cwd=sub,
                         capture_output=True, text=True, env=_clean_env(repo))
    # cwd has no plan, but the key resolved — that is a plan error, not a key one.
    assert "TTS_API_KEY" not in res.stderr


def test_narrate_env_file_override(repo, tmp_path):
    _repo_with_plan(repo)
    custom = tmp_path / "elsewhere.env"
    custom.write_text("TTS_PROVIDER=fake\n")
    res = subprocess.run(["walkthrough", "--env-file", str(custom), "narrate"],
                         cwd=repo, capture_output=True, text=True,
                         env=_clean_env(repo))
    assert res.returncode == 0, res.stderr


def test_process_env_wins_over_dotenv(repo):
    _repo_with_plan(repo)
    (repo / ".env").write_text("TTS_PROVIDER=elevenlabs\nTTS_API_KEY=from-dotenv\n")
    env = _clean_env(repo) | {"TTS_PROVIDER": "fake"}
    res = subprocess.run(["walkthrough", "narrate"], cwd=repo,
                         capture_output=True, text=True, env=env)
    assert res.returncode == 0, res.stderr


def test_missing_key_names_the_env_path_checked(repo):
    _repo_with_plan(repo)
    res = subprocess.run(["walkthrough", "narrate"], cwd=repo,
                         capture_output=True, text=True, env=_clean_env(repo))
    assert res.returncode == 3
    assert str(repo / ".env") in res.stderr
    assert "(not found)" in res.stderr


def test_secret_value_is_never_echoed(repo):
    _repo_with_plan(repo)
    (repo / ".env").write_text("TTS_PROVIDER=nonsense\nTTS_API_KEY=sk-secret-123\n")
    res = subprocess.run(["walkthrough", "narrate"], cwd=repo,
                         capture_output=True, text=True, env=_clean_env(repo))
    assert res.returncode == 3
    assert "sk-secret-123" not in res.stdout + res.stderr


# --- preflight, progress and checkpoints (#25) ---

class StubNarrator:
    """Records every call, so a test can prove none were made."""

    provider, model, voice_id = "stub", "stub-1", "v-stub"

    def __init__(self):
        self.calls: list[str] = []

    def synthesize(self, text, out, previous_text="", next_text=""):
        self.calls.append(text)
        return FakeNarrator().synthesize(text, out, previous_text, next_text)


def _ready(repo: Path, monkeypatch, narrator) -> Path:
    """A repo with a validated plan, `narrate`'s cwd, and a private cache."""
    wtdir = _repo_with_plan(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("WALKTHROUGH_CACHE", str(repo / "cache"))
    monkeypatch.setattr("walkthrough.__main__.get_narrator", lambda: narrator)
    return wtdir


def _run(*args):
    from typer.testing import CliRunner
    from walkthrough.__main__ import app
    return CliRunner().invoke(app, list(args))


def test_dry_run_reports_configuration_and_workload_without_any_request(repo, monkeypatch):
    stub = StubNarrator()
    wtdir = _ready(repo, monkeypatch, stub)
    result = _run("narrate", "--dry-run")

    assert result.exit_code == 0, result.output
    assert stub.calls == []  # the point of a dry run
    assert "provider: stub / stub-1 / voice v-stub" in result.output
    assert "chapters: 3 — 0 cached, 3 to synthesize" in result.output
    # 23 + 40 + 5 characters of narration, all of it billable
    assert "characters: 68 total, 68 to synthesize" in result.output
    # 12 words at the measured MS_PER_WORD, not the nominal rate
    assert "estimated narration: 5s" in result.output
    saved = json.loads((wtdir / "walkthrough.json").read_text())
    assert all(ch["audio"] is None for ch in saved["chapters"])


def test_dry_run_counts_cache_hits_so_the_billable_work_is_the_visible_number(repo, monkeypatch):
    stub = StubNarrator()
    _ready(repo, monkeypatch, stub)
    assert _run("narrate").exit_code == 0
    result = _run("narrate", "--dry-run")

    assert "chapters: 3 — 3 cached, 0 to synthesize" in result.output
    assert "characters: 68 total, 0 to synthesize" in result.output


def test_dry_run_with_no_cache_bills_every_chapter(repo, monkeypatch):
    stub = StubNarrator()
    _ready(repo, monkeypatch, stub)
    assert _run("narrate").exit_code == 0
    result = _run("narrate", "--dry-run", "--no-cache")

    assert "chapters: 3 — 0 cached, 3 to synthesize" in result.output
    assert "characters: 68 total, 68 to synthesize" in result.output


def test_check_synthesizes_one_short_sample_and_leaves_the_plan_alone(repo, monkeypatch):
    stub = StubNarrator()
    wtdir = _ready(repo, monkeypatch, stub)
    result = _run("narrate", "--check")

    assert result.exit_code == 0, result.output
    assert stub.calls == ["Narration check."]  # one sample, not one chapter
    assert "provider: stub / stub-1 / voice v-stub" in result.output
    assert "ok — synthesized a 1s sample" in result.output
    assert not (wtdir / "audio").exists()
    saved = json.loads((wtdir / "walkthrough.json").read_text())
    assert all(ch["audio"] is None for ch in saved["chapters"])


def test_check_needs_no_plan_because_it_only_proves_access(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("walkthrough.__main__.get_narrator", lambda: StubNarrator())
    result = _run("narrate", "--check")

    assert result.exit_code == 0, result.output
    assert "ok —" in result.output


def test_check_surfaces_the_providers_own_message_and_exits_3(repo, monkeypatch):
    from walkthrough.narrator.base import ProviderError

    class Rejecting:
        provider, model, voice_id = "stub", "stub-1", "missing-voice"

        def synthesize(self, text, out, previous_text="", next_text=""):
            raise ProviderError("HTTP 400: voice_not_found")

    _ready(repo, monkeypatch, Rejecting())
    result = _run("narrate", "--check")

    assert result.exit_code == 3
    assert "voice_not_found" in result.output  # the reason, not just "400"


def test_dry_run_and_check_are_mutually_exclusive(repo, monkeypatch):
    _ready(repo, monkeypatch, StubNarrator())
    result = _run("narrate", "--dry-run", "--check")
    assert result.exit_code == 2


def test_preflight_modes_never_echo_the_key(repo, monkeypatch):
    _repo_with_plan(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("WALKTHROUGH_CACHE", str(repo / "cache"))
    monkeypatch.setenv("TTS_PROVIDER", "fake")
    monkeypatch.setenv("TTS_API_KEY", "sk-secret-123")
    for mode in ("--dry-run", "--check"):
        result = _run("narrate", mode)
        assert result.exit_code == 0, result.output
        assert "sk-secret-123" not in result.output


def test_progress_names_every_chapter_and_the_summary_splits_the_categories(repo, monkeypatch):
    _ready(repo, monkeypatch, StubNarrator())
    result = _run("narrate")

    assert result.exit_code == 0, result.output
    for n, cid in enumerate(("c01", "c02", "c03"), 1):
        assert f"[{n}/3]" in result.output
        assert cid in result.output
    assert "3/3 clips, 0 cached, 3 synthesized (0 retried), 0 failed" in result.output

    again = _run("narrate")
    assert "3/3 clips, 3 cached, 0 synthesized (0 retried), 0 failed" in again.output


def test_a_retried_chapter_says_so_on_its_line_and_in_the_summary(repo, monkeypatch):
    class FlakyOnce:
        provider, model, voice_id = "stub", "stub-1", "v-stub"

        def __init__(self):
            self.calls = 0

        def synthesize(self, text, out, previous_text="", next_text=""):
            self.calls += 1
            if self.calls == 1:
                raise RateLimited("HTTP 429: too many concurrent requests",
                                  retry_after=0)
            return FakeNarrator().synthesize(text, out, previous_text, next_text)

    _ready(repo, monkeypatch, FlakyOnce())
    result = _run("narrate", "-j", "1")

    assert result.exit_code == 0, result.output
    assert "synthesized on attempt 2" in result.output
    assert "3/3 clips, 0 cached, 3 synthesized (1 retried), 0 failed" in result.output


def test_partial_failure_keeps_every_chapter_that_landed(repo, monkeypatch):
    from walkthrough.narrator.base import ProviderError

    class FailsOneChapter:
        provider, model, voice_id = "stub", "stub-1", "v-stub"

        def synthesize(self, text, out, previous_text="", next_text=""):
            if text.startswith("The greet function"):  # c02
                raise ProviderError("HTTP 402: quota exhausted")
            return FakeNarrator().synthesize(text, out, previous_text, next_text)

    wtdir = _ready(repo, monkeypatch, FailsOneChapter())
    monkeypatch.setattr("walkthrough.__main__.time.sleep", lambda s: None)
    result = _run("narrate", "-j", "1")

    assert result.exit_code == 3
    assert "c02 failed after 5 attempts" in result.output
    assert "quota exhausted" in result.output
    assert "2/3 clips, 0 cached, 2 synthesized (0 retried), 1 failed" in result.output
    saved = json.loads((wtdir / "walkthrough.json").read_text())
    audio = {ch["id"]: ch["audio"] for ch in saved["chapters"]}
    assert audio["c01"]["duration_ms"] > 0 and audio["c03"]["duration_ms"] > 0
    assert audio["c02"] is None


def test_an_interrupted_run_resumes_without_paying_for_what_landed(repo, monkeypatch):
    class DiesOnLastChapter:
        provider, model, voice_id = "stub", "stub-1", "v-stub"

        def synthesize(self, text, out, previous_text="", next_text=""):
            if text == "Done.":  # c03
                raise RuntimeError("connection reset")
            return FakeNarrator().synthesize(text, out, previous_text, next_text)

    wtdir = _ready(repo, monkeypatch, DiesOnLastChapter())
    monkeypatch.setattr("walkthrough.__main__.time.sleep", lambda s: None)
    assert _run("narrate", "-j", "1").exit_code == 3

    resumed = StubNarrator()
    monkeypatch.setattr("walkthrough.__main__.get_narrator", lambda: resumed)
    result = _run("narrate", "-j", "1")

    assert result.exit_code == 0, result.output
    assert resumed.calls == ["Done."]  # the two that landed are not re-billed
    assert "3/3 clips, 2 cached, 1 synthesized (0 retried), 0 failed" in result.output
    saved = json.loads((wtdir / "walkthrough.json").read_text())
    assert all(ch["audio"]["duration_ms"] > 0 for ch in saved["chapters"])
