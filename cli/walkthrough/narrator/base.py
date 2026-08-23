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


class ProviderError(Exception):
    """A provider call failed. Carries the API's own explanation, which is the
    only place the actual reason appears (bad voice id, quota, model name...)."""


class RateLimited(ProviderError):
    """HTTP 429. Distinct because it means 'slow down', not 'this failed'."""

    def __init__(self, message: str, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(message)


def check_response(r) -> None:
    """raise_for_status with the response body attached.

    httpx's own message is just the status line, so a 429 for a concurrency
    limit and a 429 for an exhausted quota look identical — and they need
    opposite responses from the caller.
    """
    if r.is_success:
        return
    detail = (r.text or "").strip().replace("\n", " ")
    if len(detail) > 300:
        detail = detail[:300] + "…"
    message = f"HTTP {r.status_code}" + (f": {detail}" if detail else "")
    if r.status_code == 429:
        raise RateLimited(message, _retry_after(r.headers.get("retry-after")))
    raise ProviderError(message)


def _retry_after(value: str | None) -> float | None:
    """Seconds form only; a HTTP-date Retry-After falls back to our own backoff."""
    try:
        return float(value) if value else None
    except ValueError:
        return None


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
