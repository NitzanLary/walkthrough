import json
from pathlib import Path

import pytest

from walkthrough import stage


def test_renderer_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("WALKTHROUGH_RENDERER", str(tmp_path))
    assert stage.renderer_dir() == tmp_path


def test_renderer_dir_defaults_into_this_repo(monkeypatch):
    monkeypatch.delenv("WALKTHROUGH_RENDERER", raising=False)
    assert stage.renderer_dir().name == "renderer"


def test_stage_assets_copies_json_and_audio(monkeypatch, tmp_path):
    src = tmp_path / "proj"
    (src / ".walkthrough" / "audio").mkdir(parents=True)
    (src / ".walkthrough" / "walkthrough.json").write_text("{}")
    (src / ".walkthrough" / "audio" / "c01.mp3").write_bytes(b"A")
    rd = tmp_path / "renderer"
    rd.mkdir()
    monkeypatch.setenv("WALKTHROUGH_RENDERER", str(rd))
    monkeypatch.chdir(src)

    out = stage.stage_assets()
    assert out == rd
    assert (rd / "public" / "walkthrough.json").read_text() == "{}"
    assert (rd / "public" / "audio" / "c01.mp3").read_bytes() == b"A"


def test_require_node_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(stage.ToolingMissing, match="node"):
        stage.require_node()
