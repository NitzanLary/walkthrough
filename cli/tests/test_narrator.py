import json
import subprocess
import wave
from pathlib import Path

import pytest

from walkthrough.narrator import cache
from walkthrough.narrator.base import get_narrator
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


@pytest.mark.xfail(
    reason="ElevenLabsNarrator ships in Task 15; this exercises the key "
           "fallback resolution but the provider module doesn't exist yet",
    strict=True, raises=ModuleNotFoundError,
)
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
