"""Disk cache: reruns pay only for changed narration."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from .base import Clip


def cache_key(provider: str, model: str, voice_id: str, text: str,
              previous_text: str = "", next_text: str = "") -> str:
    # Stitch context is part of the identity: with request stitching the same
    # sentence sounds different depending on its neighbors.
    raw = f"{provider}:{model}:{voice_id}:{previous_text}\x00{text}\x00{next_text}"
    return hashlib.sha256(raw.encode()).hexdigest()


def cache_dir() -> Path:
    env = os.environ.get("WALKTHROUGH_CACHE")
    return Path(env) if env else Path.home() / ".cache" / "walkthrough" / "audio"


def lookup(key: str) -> Clip | None:
    mp3 = cache_dir() / f"{key}.mp3"
    meta = cache_dir() / f"{key}.json"
    if not (mp3.exists() and meta.exists()):
        return None
    return Clip(path=mp3, duration_ms=json.loads(meta.read_text())["duration_ms"])


def store(key: str, src: Path, duration_ms: int) -> None:
    d = cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, d / f"{key}.mp3")
    (d / f"{key}.json").write_text(json.dumps({"duration_ms": duration_ms}))
