"""Filesystem hand-off to the renderer: copy plan + audio into renderer/public."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import AUDIO_DIR, WT_JSON


class ToolingMissing(Exception):
    pass


def renderer_dir() -> Path:
    env = os.environ.get("WALKTHROUGH_RENDERER")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "renderer"


def require_node() -> None:
    for tool in ("node", "npx"):
        if shutil.which(tool) is None:
            raise ToolingMissing(
                f"{tool} not found — install Node 20+ (https://nodejs.org) "
                f"and run `npm install` in {renderer_dir()}")


def stage_assets() -> Path:
    rd = renderer_dir()
    pub = rd / "public"
    pub.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WT_JSON, pub / "walkthrough.json")
    if AUDIO_DIR.exists():
        shutil.copytree(AUDIO_DIR, pub / "audio", dirs_exist_ok=True)
    return rd
