"""Opt-in live test: RUN_LIVE=1 LIVE_REPO=/path LIVE_BASE=main pytest -k live.
Asserts structural properties only — content quality is judged by a human
watching the result. Narration runs on the fake provider; nothing is billed."""
import json
import os
import shutil
import signal
import subprocess
from pathlib import Path

import pytest

from findings_format import parse, violations
from walkthrough import MS_PER_WORD
from walkthrough.schema import Walkthrough
from walkthrough.validate import default_budget_s

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to run")

PLAYER_PORT = 3000


def _listening_pids(port: int) -> list[int] | None:
    """PIDs listening on `port`, or None when lsof is unavailable."""
    try:
        res = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                             capture_output=True, text=True)
    except FileNotFoundError:
        return None
    return [int(pid) for pid in res.stdout.split()]


def _stop_player(port_was_free: bool) -> None:
    """The skill leaves `walkthrough view` serving after `claude -p` exits.
    On a shared host, stop only what this run started: nothing at all unless
    the port was free before it."""
    if not port_was_free:
        return
    for pid in _listening_pids(PLAYER_PORT) or []:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def test_skill_produces_valid_plan_within_budget():
    repo_env = os.environ.get("LIVE_REPO")
    if not repo_env:
        pytest.skip("LIVE_REPO not set")
    repo = Path(repo_env)
    base = os.environ.get("LIVE_BASE", "main")
    shutil.rmtree(repo / ".walkthrough", ignore_errors=True)
    # The skill narrates at hand-off; a stale .env must not pick a paid voice.
    env = {**os.environ, "TTS_PROVIDER": "fake"}
    port_was_free = _listening_pids(PLAYER_PORT) == []
    try:
        subprocess.run(
            ["claude", "-p", f"/walkthrough --base {base}",
             "--dangerously-skip-permissions"],
            cwd=repo, timeout=900, check=True, env=env)
    finally:
        _stop_player(port_was_free)

    plan_path = repo / ".walkthrough" / "walkthrough.json"
    assert plan_path.exists()
    res = subprocess.run(["walkthrough", "validate"], cwd=repo,
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr

    plan = json.loads(plan_path.read_text())
    assert plan["chapters"][0]["action"] == "overview"
    assert plan["chapters"][-1]["action"] == "closing"

    budget_s = default_budget_s(Walkthrough.model_validate(plan))
    words = sum(len(c["narration"].split()) for c in plan["chapters"])
    est_s = words * MS_PER_WORD / 1000  # the measured speaking rate
    assert est_s <= budget_s * 1.25, f"estimated {est_s:.0f}s vs budget {budget_s:.0f}s"

    findings_path = repo / ".walkthrough" / "review" / "findings.md"
    assert findings_path.exists(), "the listener pass wrote no findings.md"
    text = findings_path.read_text()
    assert violations(text) == []
    findings, _, _ = parse(text)
    print(f"listener findings: {len(findings)} "
          f"({sum(f.severity == 'blocks' for f in findings.values())} blocks)")
