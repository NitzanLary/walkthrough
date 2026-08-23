from __future__ import annotations

import os
from pathlib import Path

import httpx
from mutagen.mp3 import MP3

from .base import Clip, check_response


class OpenAINarrator:
    provider = "openai"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = os.environ.get("TTS_MODEL", "gpt-4o-mini-tts")
        self.voice_id = os.environ.get("TTS_VOICE_ID", "alloy")

    def synthesize(self, text: str, out: Path,
                   previous_text: str = "", next_text: str = "") -> Clip:
        # OpenAI TTS has no request stitching; context args are accepted for
        # protocol compatibility and ignored.
        r = httpx.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "voice": self.voice_id,
                  "input": text, "response_format": "mp3"},
            timeout=120,
        )
        check_response(r)
        out.write_bytes(r.content)
        duration_ms = round(MP3(out).info.length * 1000)
        return Clip(path=out, duration_ms=duration_ms)
