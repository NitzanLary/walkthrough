import base64
import json
from pathlib import Path

import httpx

from walkthrough.narrator.elevenlabs import ElevenLabsNarrator
from walkthrough.narrator.openai import OpenAINarrator


class FakeResponse:
    def __init__(self, json_data=None, content=b""):
        self._json, self.content = json_data, content

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_elevenlabs_decodes_audio_and_exact_duration(tmp_path, monkeypatch):
    payload = {
        "audio_base64": base64.b64encode(b"MP3DATA").decode(),
        "alignment": {
            "characters": ["h", "i"],
            "character_start_times_seconds": [0.0, 0.5],
            "character_end_times_seconds": [0.5, 1.42],
        },
    }
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"], seen["kwargs"] = url, kwargs
        return FakeResponse(json_data=payload)

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setenv("TTS_VOICE_ID", "voice123")
    n = ElevenLabsNarrator(api_key="k")
    out = tmp_path / "c01.mp3"
    clip = n.synthesize("hi", out, previous_text="before.", next_text="after.")
    assert "voice123/with-timestamps" in seen["url"]
    assert seen["kwargs"]["headers"]["xi-api-key"] == "k"
    body = seen["kwargs"]["json"]
    assert body["previous_text"] == "before." and body["next_text"] == "after."
    assert body["voice_settings"] == {"stability": 0.5, "similarity_boost": 0.75,
                                      "style": 0.3}
    assert out.read_bytes() == b"MP3DATA"
    assert clip.duration_ms == 1420
    words = json.loads((tmp_path / "c01.words.json").read_text())
    assert words["characters"] == ["h", "i"]


def test_elevenlabs_defaults_to_george_and_multilingual(monkeypatch):
    monkeypatch.delenv("TTS_VOICE_ID", raising=False)
    monkeypatch.delenv("TTS_MODEL", raising=False)
    n = ElevenLabsNarrator(api_key="k")
    assert n.voice_id == "JBFqnCBsd6RMkjVDRZzb"  # George, the skill's narrative voice
    assert n.model == "eleven_multilingual_v2"


def test_elevenlabs_omits_empty_stitch_context(tmp_path, monkeypatch):
    payload = {
        "audio_base64": base64.b64encode(b"X").decode(),
        "alignment": {"characters": ["x"], "character_start_times_seconds": [0.0],
                      "character_end_times_seconds": [0.2]},
    }
    seen = {}

    def fake_post(url, **kwargs):
        seen["kwargs"] = kwargs
        return FakeResponse(json_data=payload)

    monkeypatch.setattr(httpx, "post", fake_post)
    ElevenLabsNarrator(api_key="k").synthesize("x", tmp_path / "c.mp3")
    body = seen["kwargs"]["json"]
    assert "previous_text" not in body and "next_text" not in body


def test_openai_duration_via_mutagen(tmp_path, monkeypatch):
    def fake_post(url, **kwargs):
        return FakeResponse(content=b"ID3MP3BYTES")

    monkeypatch.setattr(httpx, "post", fake_post)

    class FakeMP3:
        def __init__(self, path):
            self.info = type("I", (), {"length": 2.5})()

    import walkthrough.narrator.openai as mod
    monkeypatch.setattr(mod, "MP3", FakeMP3)

    n = OpenAINarrator(api_key="k")
    clip = n.synthesize("hello there", tmp_path / "c01.mp3")
    assert (tmp_path / "c01.mp3").read_bytes() == b"ID3MP3BYTES"
    assert clip.duration_ms == 2500
