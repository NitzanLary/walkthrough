"""Opt-in live test: RUN_LIVE=1 LIVE_REPO=/path LIVE_BASE=main pytest -k live.
Asserts structural properties only — content quality is judged by a human
watching the result."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to run")


def test_skill_produces_valid_plan_within_budget():
    repo_env = os.environ.get("LIVE_REPO")
    if not repo_env:
        pytest.skip("LIVE_REPO not set")
    repo = Path(repo_env)
    base = os.environ.get("LIVE_BASE", "main")
    shutil.rmtree(repo / ".walkthrough", ignore_errors=True)
    subprocess.run(
        ["claude", "-p", f"/walkthrough --base {base}", "--dangerously-skip-permissions"],
        cwd=repo, timeout=900, check=True)

    plan_path = repo / ".walkthrough" / "walkthrough.json"
    assert plan_path.exists()
    res = subprocess.run(["walkthrough", "validate"], cwd=repo,
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr

    plan = json.loads(plan_path.read_text())
    assert plan["chapters"][0]["action"] == "overview"
    assert plan["chapters"][-1]["action"] == "closing"

    changed = plan["meta"]["stats"]["added"] + plan["meta"]["stats"]["removed"]
    budget_s = min(600, max(60, changed * 0.45))
    words = sum(len(c["narration"].split()) for c in plan["chapters"])
    est_s = words / 2.5  # the skill's own words-per-second planning rate
    assert est_s <= budget_s * 1.25, f"estimated {est_s:.0f}s vs budget {budget_s:.0f}s"
