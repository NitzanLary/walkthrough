import json
import subprocess
from pathlib import Path

from walkthrough import CHAPTER_BUDGET_MS, MS_PER_WORD
from walkthrough.schema import Walkthrough
from walkthrough.validate import (check_anchors, check_chapter_order,
                                  check_file_refs, check_focus_ranges,
                                  check_narration_budget)

from conftest import commit_file, git
from test_schema import make_plan

AFTER = "import os\n\n\ndef greet(name):\n    return f\"hi {name}\"\n\n\ndef main():\n    print(greet(os.environ[\"USER\"]))\n"


def filled_plan(**overrides) -> Walkthrough:
    p = make_plan(**overrides)
    p["files"][0]["before"] = ""
    p["files"][0]["after"] = AFTER
    p["chapters"][1]["focus"] = {"start": 4, "end": 5, "anchor": "def greet(name):"}
    return Walkthrough.model_validate(p)


def test_anchor_exact_match_no_change():
    wt = filled_plan()
    warnings, errors = check_anchors(wt)
    assert (warnings, errors) == ([], [])
    assert wt.chapters[1].focus.start == 4


def test_anchor_drift_auto_corrected_with_warning():
    wt = filled_plan()
    wt.chapters[1].focus.start, wt.chapters[1].focus.end = 6, 7  # off by +2
    warnings, errors = check_anchors(wt)
    assert errors == []
    assert len(warnings) == 1 and "-2" in warnings[0]
    assert (wt.chapters[1].focus.start, wt.chapters[1].focus.end) == (4, 5)


def test_anchor_missing_is_error_with_location():
    wt = filled_plan()
    wt.chapters[1].focus.anchor = "def nonexistent():"
    warnings, errors = check_anchors(wt)
    assert warnings == [] and len(errors) == 1
    assert "chapters[1]" in errors[0] and "not found" in errors[0]


def test_anchor_ambiguous_lists_candidates():
    wt = filled_plan()
    wt.files[0].after = "x = 1\nx = 1\nx = 1\n"
    wt.chapters[1].focus.start, wt.chapters[1].focus.end = 2, 2
    wt.chapters[1].focus.anchor = "x = 1"
    # anchor matches line 2 exactly -> fine; shift to a mismatch to force search
    wt.chapters[1].focus.anchor = "x  =  1"  # trimmed compare still mismatches
    warnings, errors = check_anchors(wt)
    assert len(errors) == 1 and "not found" in errors[0]
    # now a real ambiguity: anchor text present on several lines, none at start
    wt = filled_plan()
    wt.files[0].after = "y = 0\nx = 1\nz = 2\nx = 1\n"
    wt.chapters[1].focus.start, wt.chapters[1].focus.end = 1, 1
    wt.chapters[1].focus.anchor = "x = 1"
    warnings, errors = check_anchors(wt)
    assert len(errors) == 1 and "ambiguous" in errors[0]
    assert "2" in errors[0] and "4" in errors[0]


def test_anchor_compared_whitespace_trimmed():
    wt = filled_plan()
    wt.chapters[1].focus.anchor = "   def greet(name):   "
    warnings, errors = check_anchors(wt)
    assert (warnings, errors) == ([], [])


def test_deleted_file_anchor_checked_against_before():
    wt = filled_plan()
    wt.files[0].status = "deleted"
    wt.files[0].before, wt.files[0].after = AFTER, ""
    warnings, errors = check_anchors(wt)
    assert (warnings, errors) == ([], [])


def test_file_ref_and_range_checks():
    wt = filled_plan()
    wt.chapters[1].file = "missing.py"
    assert any("missing.py" in e for e in check_file_refs(wt))

    wt = filled_plan()
    wt.chapters[1].focus.start, wt.chapters[1].focus.end = 200, 212
    errs = check_focus_ranges(wt)
    assert len(errs) == 1
    assert "chapters[1].focus.end (212) exceeds line count of greet.py (9)" in errs[0]


def test_narration_budget_warns_only_past_the_chapter_ceiling():
    ceiling_words = CHAPTER_BUDGET_MS // MS_PER_WORD
    wt = filled_plan()
    wt.chapters[1].narration = " ".join(["word"] * ceiling_words)
    assert check_narration_budget(wt) == []

    wt.chapters[1].narration = " ".join(["word"] * (ceiling_words + 20))
    warnings = check_narration_budget(wt)
    assert len(warnings) == 1
    assert "chapters[1] (c02)" in warnings[0]
    assert f"{ceiling_words + 20} words" in warnings[0]
    assert "split" in warnings[0]


def test_cli_validate_reports_budget_warning_and_still_exits_0(repo):
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", AFTER)
    p = make_plan()
    p["meta"]["base_sha"], p["meta"]["head_sha"] = base, head
    p["files"][0] = {"path": "greet.py", "language": None, "status": "modified",
                     "old_path": None, "before": None, "after": None}
    p["chapters"][1]["focus"] = {"start": 4, "end": 5, "anchor": "def greet(name):"}
    p["chapters"][1]["narration"] = " ".join(["word"] * 120)
    wtdir = repo / ".walkthrough"
    wtdir.mkdir()
    (wtdir / "walkthrough.json").write_text(json.dumps(p))

    res = subprocess.run(["walkthrough", "validate"], cwd=repo,
                         capture_output=True, text=True)
    # Overshoot is a quality problem, not a broken plan: warn, do not block.
    assert res.returncode == 0, res.stderr
    assert "warning:" in res.stdout and "120 words" in res.stdout


def test_chapter_order_checks():
    wt = filled_plan()
    wt.chapters[0].action = "closing"
    assert any("overview" in e for e in check_chapter_order(wt))


def test_cli_validate_end_to_end_fills_and_exits_0(repo):
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", AFTER)
    p = make_plan()
    p["meta"]["base_sha"], p["meta"]["head_sha"] = base, head
    p["files"][0] = {"path": "greet.py", "language": None, "status": "modified",
                     "old_path": None, "before": None, "after": None}
    p["chapters"][1]["focus"] = {"start": 4, "end": 5, "anchor": "def greet(name):"}
    wtdir = repo / ".walkthrough"
    wtdir.mkdir()
    (wtdir / "walkthrough.json").write_text(json.dumps(p))

    res = subprocess.run(["walkthrough", "validate"], cwd=repo,
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    saved = json.loads((wtdir / "walkthrough.json").read_text())
    assert saved["files"][0]["after"] == AFTER
    assert saved["files"][0]["language"] == "python"


def test_cli_validate_numbered_errors_exit_2(repo):
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", AFTER)
    p = make_plan()
    p["meta"]["base_sha"], p["meta"]["head_sha"] = base, head
    p["files"][0] = {"path": "greet.py", "language": None, "status": "modified",
                     "old_path": None, "before": None, "after": None}
    p["chapters"][1]["file"] = "missing.py"
    wtdir = repo / ".walkthrough"
    wtdir.mkdir()
    (wtdir / "walkthrough.json").write_text(json.dumps(p))

    res = subprocess.run(["walkthrough", "validate"], cwd=repo,
                         capture_output=True, text=True)
    assert res.returncode == 2
    assert "1. " in res.stderr


def test_cli_validate_duplicate_chapter_id_exits_2(repo):
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", AFTER)
    p = make_plan()
    p["meta"]["base_sha"], p["meta"]["head_sha"] = base, head
    p["files"][0] = {"path": "greet.py", "language": None, "status": "modified",
                     "old_path": None, "before": None, "after": None}
    p["chapters"][1]["focus"] = {"start": 4, "end": 5, "anchor": "def greet(name):"}
    p["chapters"][2]["id"] = p["chapters"][0]["id"]
    wtdir = repo / ".walkthrough"
    wtdir.mkdir()
    (wtdir / "walkthrough.json").write_text(json.dumps(p))

    res = subprocess.run(["walkthrough", "validate"], cwd=repo,
                         capture_output=True, text=True)
    assert res.returncode == 2
    assert "duplicate id 'c01'" in res.stderr
