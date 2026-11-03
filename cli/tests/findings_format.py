"""The findings.md contract. The listener writes the Findings table
(skills/walkthrough/references/listener-prompt.md) and the author appends the
Triage table (references/triage.md). The offline contract tests and the live
skill test both judge files with this one reader."""
from __future__ import annotations

import re
from dataclasses import dataclass

TYPES = {"LOST", "JUMP", "WHY", "ORDER", "GAP", "MISMATCH"}
SEVERITIES = {"blocks", "minor"}
DECISIONS = {"FIX", "RULING", "N/A"}
_RULING_NOTE = re.compile(r"reason:\s*\S.*cost if wrong:\s*\S", re.IGNORECASE)


@dataclass
class Finding:
    id: str
    chapter: str
    type: str
    severity: str
    text: str


@dataclass
class Decision:
    id: str
    decision: str
    note: str


def _sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return out


def _rows(lines: list[str]) -> list[list[str]]:
    table = [[c.strip() for c in line.strip().strip("|").split("|")]
             for line in lines if line.strip().startswith("|")]
    # table[0] is the header; the |----| separator is all dashes.
    return [r for r in table[1:] if not all(set(c) <= set("-: ") for c in r)]


def parse(text: str) -> tuple[dict[str, Finding], list[Decision], list[str]]:
    sections = _sections(text)
    if "findings" not in sections:
        return {}, [], ["no '## Findings' section"]
    problems: list[str] = []
    findings: dict[str, Finding] = {}
    for r in _rows(sections["findings"]):
        if len(r) != 5:
            problems.append(f"findings row has {len(r)} cells, want 5: {r}")
            continue
        f = Finding(*r)
        if f.type not in TYPES:
            problems.append(f"{f.id}: unknown type {f.type!r}")
        if f.severity not in SEVERITIES:
            problems.append(f"{f.id}: unknown severity {f.severity!r}")
        if f.id in findings:
            problems.append(f"{f.id}: duplicate finding id")
        findings[f.id] = f
    decisions: list[Decision] = []
    for r in _rows(sections.get("triage", [])):
        if len(r) != 3:
            problems.append(f"triage row has {len(r)} cells, want 3: {r}")
            continue
        decisions.append(Decision(*r))
    return findings, decisions, problems


def violations(text: str) -> list[str]:
    """Every breach of the format or the triage rules; empty means sound."""
    findings, decisions, problems = parse(text)
    if findings and "triage" not in _sections(text):
        return problems + ["findings exist but there is no '## Triage' section"]
    seen: dict[str, Decision] = {}
    for d in decisions:
        if d.id not in findings:
            problems.append(f"{d.id}: triage row for an unknown finding")
            continue
        if d.id in seen:
            problems.append(f"{d.id}: triaged twice")
            continue
        seen[d.id] = d
        if d.decision not in DECISIONS:
            problems.append(f"{d.id}: unknown decision {d.decision!r}")
        elif not d.note:
            problems.append(f"{d.id}: empty note")
        elif d.decision == "RULING" and not _RULING_NOTE.search(d.note):
            problems.append(
                f"{d.id}: a RULING note needs 'reason: …' and 'cost if wrong: …'")
    for fid, f in findings.items():
        d = seen.get(fid)
        if d is None:
            problems.append(f"{fid}: no triage row")
        elif f.severity == "blocks" and d.decision == "N/A":
            problems.append(f"{fid}: a blocks finding must be FIX or RULING, not N/A")
    return problems
