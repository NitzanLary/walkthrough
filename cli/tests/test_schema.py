import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from walkthrough.schema import Walkthrough

REPO = Path(__file__).resolve().parents[2]


def make_plan(**overrides) -> dict:
    plan = {
        "version": 1,
        "meta": {
            "repo": "demo", "base": "main", "head": "feat/x",
            "base_sha": "a" * 40, "head_sha": "b" * 40,
            "title": "Add greeting", "summary": "Adds a greeting helper.",
            "stats": {"files": 1, "added": 4, "removed": 0},
            "skipped": [], "generated_at": "2026-08-21T00:00:00Z",
        },
        "files": [{"path": "greet.py", "language": "python", "status": "added",
                   "old_path": None, "before": None, "after": None}],
        "chapters": [
            {"id": "c01", "title": "Overview", "action": "overview",
             "file": None, "focus": None, "narration": "Adds a greeting helper.", "audio": None},
            {"id": "c02", "title": "greet", "action": "zoom", "file": "greet.py",
             "focus": {"start": 1, "end": 2, "anchor": "def greet(name):"},
             "narration": "The greet function formats a salutation.", "audio": None},
            {"id": "c03", "title": "Wrap-up", "action": "closing",
             "file": None, "focus": None, "narration": "Done.", "audio": None},
        ],
    }
    plan.update(overrides)
    return plan


def test_valid_agent_plan_loads_without_before_after_or_audio():
    wt = Walkthrough.model_validate(make_plan())
    assert wt.files[0].before is None
    assert wt.chapters[0].audio is None


def test_focus_span_over_60_rejected():
    p = make_plan()
    p["chapters"][1]["focus"] = {"start": 1, "end": 61, "anchor": "x"}
    with pytest.raises(ValidationError, match="60"):
        Walkthrough.model_validate(p)


def test_focus_end_before_start_rejected():
    p = make_plan()
    p["chapters"][1]["focus"] = {"start": 10, "end": 5, "anchor": "x"}
    with pytest.raises(ValidationError):
        Walkthrough.model_validate(p)


def test_zoom_without_focus_rejected():
    p = make_plan()
    p["chapters"][1]["focus"] = None
    with pytest.raises(ValidationError, match="focus"):
        Walkthrough.model_validate(p)


def test_overview_with_file_rejected():
    p = make_plan()
    p["chapters"][0]["file"] = "greet.py"
    with pytest.raises(ValidationError):
        Walkthrough.model_validate(p)


def test_renamed_requires_old_path():
    p = make_plan()
    p["files"][0]["status"] = "renamed"
    with pytest.raises(ValidationError, match="old_path"):
        Walkthrough.model_validate(p)


def test_duplicate_chapter_ids_rejected():
    p = make_plan()
    p["chapters"][2]["id"] = p["chapters"][0]["id"]
    with pytest.raises(ValidationError, match="duplicate id 'c01'"):
        Walkthrough.model_validate(p)


def test_duplicate_file_paths_rejected():
    p = make_plan()
    p["files"].append({"path": "greet.py", "language": "python", "status": "added",
                        "old_path": None, "before": None, "after": None})
    with pytest.raises(ValidationError, match="duplicate path 'greet.py'"):
        Walkthrough.model_validate(p)


def test_schema_json_in_sync_with_models():
    emitted = Walkthrough.model_json_schema()
    on_disk = json.loads((REPO / "skills/walkthrough/schema.json").read_text())
    assert emitted == on_disk


def test_small_example_is_schema_valid_agent_form():
    data = json.loads((REPO / "skills/walkthrough/examples/small.json").read_text())
    wt = Walkthrough.model_validate(data)
    assert all(f.before is None and f.after is None for f in wt.files)
    assert all(c.audio is None for c in wt.chapters)
    assert wt.chapters[0].action == "overview"
    assert wt.chapters[-1].action == "closing"
