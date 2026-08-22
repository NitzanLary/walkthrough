"""Default narrator. The with-timestamps endpoint makes duration_ms exact and
yields word timestamps for future word-triggered camera moves (unused in MVP)."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import httpx

from .base import Clip


# Defaults follow the official ElevenLabs skill: multilingual_v2 for
# high-quality long-form narration (flash is for real-time latency), George as
# the narrative voice, and voice_settings per the Remotion voiceover guide.
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George (male, narrative)
VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.3}


class ElevenLabsNarrator:
    provider = "elevenlabs"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = os.environ.get("TTS_MODEL", DEFAULT_MODEL)
        self.voice_id = os.environ.get("TTS_VOICE_ID", DEFAULT_VOICE)

    def synthesize(self, text: str, out: Path,
                   previous_text: str = "", next_text: str = "") -> Clip:
        body: dict = {"text": text, "model_id": self.model,
                      "voice_settings": VOICE_SETTINGS}
        # Request stitching: neighbors keep tone continuous across clips.
        if previous_text:
            body["previous_text"] = previous_text
        if next_text:
            body["next_text"] = next_text
        r = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
            f"/with-timestamps?output_format=mp3_44100_128",
            headers={"xi-api-key": self.api_key},
            json=body,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        out.write_bytes(base64.b64decode(data["audio_base64"]))
        alignment = data["alignment"]
        duration_ms = round(alignment["character_end_times_seconds"][-1] * 1000)
        out.with_name(out.stem + ".words.json").write_text(json.dumps(alignment))
        return Clip(path=out, duration_ms=duration_ms)
