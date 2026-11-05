import json
import subprocess
from pathlib import Path

import pytest

from walkthrough import CHAPTER_BUDGET_MS, MS_PER_WORD
from walkthrough.schema import FileEntry, Walkthrough
from walkthrough.validate import (check_anchors, check_chapter_order,
                                  check_file_refs, check_focus_ranges,
                                  check_narration_budget, check_total_budget,
                                  check_uncovered_files, check_zoom_span,
                                  default_budget_s)

from conftest import commit_file, git
from test_schema import REPO, make_plan

AFTER = "import os\n\n\ndef greet(name):\n    return f\"hi {name}\"\n\n\ndef main():\n    print(greet(os.environ[\"USER\"]))\n"


def filled_plan(**overrides) -> Walkthrough:
    p = make_plan(**overrides)
    p["files"][0]["before"] = ""
    p["files"][0]["after"] = AFTER
    p["chapters"][1]["focus"] = {"start": 4, "end": 5, "anchor": "def greet(name):"}
    return Walkthrough.model_validate(p)


LONG = "".join(f"line {n}\n" for n in range(1, 31))


def cli_plan(repo: Path, after: str = AFTER) -> dict:
    """A plan whose greet.py is committed in `repo`, ready for the CLI."""
    base = commit_file(repo, "greet.py", "")
    head = commit_file(repo, "greet.py", after)
    p = make_plan()
    p["meta"]["base_sha"], p["meta"]["head_sha"] = base, head
    p["files"][0] = {"path": "greet.py", "language": None, "status": "modified",
                     "old_path": None, "before": None, "after": None}
    p["chapters"][1]["focus"] = {"start": 4, "end": 5, "anchor": "def greet(name):"}
    return p


def run_validate(repo: Path, p: dict, *args: str) -> subprocess.CompletedProcess:
    wtdir = repo / ".walkthrough"
    wtdir.mkdir(exist_ok=True)
    (wtdir / "walkthrough.json").write_text(json.dumps(p))
    return subprocess.run(["walkthrough", "validate", *args], cwd=repo,
                          capture_output=True, text=True)


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


def test_zoom_span_20_ok_21_is_error():
    wt = filled_plan()
    wt.files[0].after = LONG
    wt.chapters[1].focus.start, wt.chapters[1].focus.end = 1, 20
    wt.chapters[1].focus.anchor = "line 1"
    assert check_zoom_span(wt) == []

    wt.chapters[1].focus.end = 21
    errors = check_zoom_span(wt)
    assert len(errors) == 1
    assert "chapters[1] (c02)" in errors[0]
    assert "spans 21 lines" in errors[0]
    assert "'show'" in errors[0]


def test_zoom_span_ignores_other_actions():
    wt = filled_plan()
    wt.files[0].after = LONG
    wt.chapters[1].action = "show"
    wt.chapters[1].focus.start, wt.chapters[1].focus.end = 1, 40
    assert check_zoom_span(wt) == []


def test_cli_validate_rejects_tall_zoom_exit_2(repo):
    p = cli_plan(repo, after=LONG)
    p["chapters"][1]["focus"] = {"start": 1, "end": 21, "anchor": "line 1"}
    res = run_validate(repo, p)
    assert res.returncode == 2
    assert "zoom focus spans 21 lines" in res.stderr


def test_uncovered_file_warns_with_path_and_fixes():
    wt = filled_plan()
    assert check_uncovered_files(wt) == []

    wt.files.append(FileEntry(path="util.py", status="modified",
                              before="", after="x = 1\n"))
    warnings = check_uncovered_files(wt)
    assert len(warnings) == 1
    assert "files[1] 'util.py' is shown by no chapter" in warnings[0]
    assert "incidental chapter" in warnings[0]
    assert "meta.skipped" in warnings[0]


def test_cli_validate_warns_on_uncovered_file_and_exits_0(repo):
    commit_file(repo, "util.py", "x = 1\n")
    p = cli_plan(repo)
    p["files"].append({"path": "util.py", "language": None, "status": "modified",
                       "old_path": None, "before": None, "after": None})
    res = run_validate(repo, p)
    assert res.returncode == 0, res.stderr
    assert "warning: files[1] 'util.py' is shown by no chapter" in res.stdout


def _set_total_words(wt: Walkthrough, n: int) -> None:
    wt.chapters[0].narration = " ".join(["word"] * (n - 2))
    wt.chapters[1].narration = "one"
    wt.chapters[2].narration = "two"


def test_total_budget_at_limit_ok_one_word_over_warns():
    wt = filled_plan()
    _set_total_words(wt, 200)  # 200 × 435 ms = exactly 87 s
    assert check_total_budget(wt, 87) == []

    _set_total_words(wt, 201)
    warnings = check_total_budget(wt, 87)
    assert len(warnings) == 1
    assert "201 words" in warnings[0]
    assert "over the 87s budget" in warnings[0]
    assert "Merge" in warnings[0]
    assert "chapters[0] (" in warnings[0]
    # 201 × 435 ms = 87.4 s: rounding would print "87s spoken, over the 87s".
    assert "about 88s spoken" in warnings[0]


def test_total_budget_estimate_prints_above_a_fractional_budget():
    wt = filled_plan()
    _set_total_words(wt, 142)  # 142 × 435 ms = 61.77 s
    warnings = check_total_budget(wt, 61.65)
    assert len(warnings) == 1
    assert "about 62s spoken, over the 61s budget" in warnings[0]


def test_total_budget_names_the_longest_chapter_wherever_it_is():
    wt = filled_plan()
    wt.chapters[0].narration = "short"
    wt.chapters[1].narration = "a bit longer"
    wt.chapters[2].narration = " ".join(["word"] * 250)
    warnings = check_total_budget(wt, 87)
    assert len(warnings) == 1
    assert "chapters[2] (" in warnings[0]
    assert "250 words." in warnings[0]


@pytest.mark.parametrize("added,removed,want", [
    (4, 0, 60), (1000, 0, 450), (900, 100, 450), (2000, 0, 600)])
def test_default_budget_is_clamped_from_kept_stats(added, removed, want):
    wt = filled_plan()
    wt.meta.stats.added, wt.meta.stats.removed = added, removed
    got = default_budget_s(wt)
    assert got == pytest.approx(want)
    assert isinstance(got, float)


def test_cli_validate_budget_default_and_override(repo):
    p = cli_plan(repo)  # stats +4 −0 → default budget 60 s
    p["chapters"][0]["narration"] = " ".join(["word"] * 200)  # ~90 s in total
    res = run_validate(repo, p)
    assert res.returncode == 0, res.stderr
    assert "over the 60s budget" in res.stdout

    res = run_validate(repo, p, "--budget", "120")
    assert res.returncode == 0, res.stderr
    assert "s budget" not in res.stdout


def test_small_example_fits_its_own_budget():
    data = json.loads((REPO / "skills/walkthrough/examples/small.json").read_text())
    wt = Walkthrough.model_validate(data)
    assert check_total_budget(wt, default_budget_s(wt)) == []
    assert check_narration_budget(wt) == []
