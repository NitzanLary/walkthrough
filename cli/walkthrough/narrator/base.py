from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class Clip:
    path: Path
    duration_ms: int


class Narrator(Protocol):
    provider: str
    model: str
    voice_id: str

    def synthesize(self, text: str, out: Path,
                   previous_text: str = "", next_text: str = "") -> Clip: ...


class MissingKeyError(Exception):
    def __init__(self, var_name: str):
        self.var_name = var_name
        super().__init__(f"missing environment variable {var_name}")


# Provider-specific key env vars accepted when TTS_API_KEY is unset — the
# official ElevenLabs/OpenAI setup flows write these names into .env.
_KEY_FALLBACK = {"elevenlabs": "ELEVENLABS_API_KEY", "openai": "OPENAI_API_KEY"}


def get_narrator() -> Narrator:
    provider = os.environ.get("TTS_PROVIDER", "elevenlabs")
    if provider == "fake":
        from .fake import FakeNarrator
        return FakeNarrator()
    if provider not in _KEY_FALLBACK:
        raise ValueError(f"unknown TTS_PROVIDER {provider!r} (elevenlabs | openai | fake)")
    key = os.environ.get("TTS_API_KEY") or os.environ.get(_KEY_FALLBACK[provider])
    if not key:
        raise MissingKeyError(f"TTS_API_KEY (or {_KEY_FALLBACK[provider]})")
    if provider == "elevenlabs":
        from .elevenlabs import ElevenLabsNarrator
        return ElevenLabsNarrator(api_key=key)
    from .openai import OpenAINarrator
    return OpenAINarrator(api_key=key)
