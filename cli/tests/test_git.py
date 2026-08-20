from pathlib import Path

from walkthrough.git import fill_contents, show_file
from walkthrough.schema import Walkthrough

from conftest import commit_file, git
from test_schema import make_plan


def _plan_for(repo, base_sha, head_sha, files):
    p = make_plan()
    p["meta"]["base_sha"] = base_sha
    p["meta"]["head_sha"] = head_sha
    p["files"] = files
    # keep chapters consistent with the first file
    p["chapters"][1]["file"] = files[0]["path"]
    return Walkthrough.model_validate(p)


def _f(path, status, old_path=None, language=None):
    return {"path": path, "status": status, "old_path": old_path,
            "language": language, "before": None, "after": None}


def test_added_modified_deleted_renamed(repo):
    base = commit_file(repo, "mod.py", "old\n")
    commit_file(repo, "del.py", "gone\n")
    commit_file(repo, "old_name.py", "same\n")
    base = git(repo, "rev-parse", "HEAD")
    commit_file(repo, "mod.py", "new\n")
    commit_file(repo, "add.py", "fresh\n")
    (repo / "del.py").unlink()
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "del")
    git(repo, "mv", "old_name.py", "new_name.py")
    git(repo, "commit", "-m", "mv")
    head = git(repo, "rev-parse", "HEAD")

    wt = _plan_for(repo, base, head, [
        _f("add.py", "added"),
        _f("mod.py", "modified"),
        _f("del.py", "deleted"),
        _f("new_name.py", "renamed", old_path="old_name.py"),
    ])
    errors = fill_contents(wt, repo)
    assert errors == []
    by = {f.path: f for f in wt.files}
    assert (by["add.py"].before, by["add.py"].after) == ("", "fresh\n")
    assert (by["mod.py"].before, by["mod.py"].after) == ("old\n", "new\n")
    assert (by["del.py"].before, by["del.py"].after) == ("gone\n", "")
    assert (by["new_name.py"].before, by["new_name.py"].after) == ("same\n", "same\n")
    assert by["add.py"].language == "python"  # detected from extension


def test_extraction_pinned_to_shas_survives_new_commit(repo):
    base = commit_file(repo, "a.py", "v1\n")
    head = commit_file(repo, "a.py", "v2\n")
    commit_file(repo, "a.py", "v3 — moved on\n")  # branch advances after planning

    wt = _plan_for(repo, base, head, [_f("a.py", "modified")])
    assert fill_contents(wt, repo) == []
    assert wt.files[0].after == "v2\n"


def test_missing_path_reports_error_not_exception(repo):
    base = commit_file(repo, "a.py", "v1\n")
    head = commit_file(repo, "a.py", "v2\n")
    wt = _plan_for(repo, base, head, [_f("nope.py", "modified")])
    errors = fill_contents(wt, repo)
    assert len(errors) == 1 and "nope.py" in errors[0]
