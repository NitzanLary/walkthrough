"""Silent clips with word-count-derived durations — tests and renderer work
without a TTS key. Content is a WAV container; browsers and Remotion decode by
content sniffing, so the .mp3 file name from the contract still plays."""
from __future__ import annotations

import wave
from pathlib import Path

from .. import MS_PER_WORD
from .base import Clip


class FakeNarrator:
    provider = "fake"
    model = "fake-1"
    voice_id = "v1"

    def synthesize(self, text: str, out: Path,
                   previous_text: str = "", next_text: str = "") -> Clip:
        duration_ms = max(1000, len(text.split()) * MS_PER_WORD)
        n_frames = int(44100 * duration_ms / 1000)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            w.writeframes(b"\x00\x00" * n_frames)
        return Clip(path=out, duration_ms=duration_ms)
