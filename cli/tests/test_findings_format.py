import re
from pathlib import Path

from findings_format import parse, violations

REFS = Path(__file__).resolve().parents[2] / "skills/walkthrough/references"

HEAD = ("# Listener findings\n\n## Findings\n\n"
        "| ID | Chapter | Type | Severity | Finding |\n"
        "|----|---------|------|----------|---------|\n")
TRIAGE = "\n## Triage\n\n| ID | Decision | Note |\n|----|----------|------|\n"


def doc(findings: list[str], triage: list[str] | None = None) -> str:
    text = HEAD + "".join(f"{r}\n" for r in findings)
    if triage is not None:
        text += TRIAGE + "".join(f"{r}\n" for r in triage)
    return text


def example(name: str) -> str:
    """The first ```markdown block in a reference file: its worked example."""
    m = re.search(r"```markdown\n(.*?)```", (REFS / name).read_text(), re.S)
    assert m, f"{name} has no ```markdown example"
    return m.group(1)


def test_listener_prompt_example_parses_cleanly():
    findings, _, problems = parse(example("listener-prompt.md"))
    assert problems == []
    assert findings


def test_listener_prompt_has_one_dispatch_separator_and_placeholders():
    text = (REFS / "listener-prompt.md").read_text()
    assert text.splitlines().count("---") == 1
    prompt = text.split("\n---\n", 1)[1]
    for slot in ("{MARKDOWN}", "{DIFF}", "{FINDINGS}"):
        assert slot in prompt


def test_triage_example_satisfies_every_rule():
    text = example("triage.md")
    assert violations(text) == []
    _, decisions, _ = parse(text)
    assert {d.decision for d in decisions} == {"FIX", "RULING", "N/A"}


def test_nothing_important_needs_no_triage():
    assert violations(HEAD + "\nnothing important\n") == []


def test_blocks_finding_cannot_be_na():
    text = doc(["| F1 | 2 | GAP | blocks | x |"], ["| F1 | N/A | misread |"])
    assert "F1: a blocks finding must be FIX or RULING, not N/A" in violations(text)


def test_ruling_needs_reason_and_cost():
    text = doc(["| F1 | 2 | WHY | blocks | x |"], ["| F1 | RULING | clear enough |"])
    assert any("cost if wrong" in p for p in violations(text))

    text = doc(["| F1 | 2 | WHY | blocks | x |"],
               ["| F1 | RULING | reason: shown in chapter 3 — cost if wrong: one pause |"])
    assert violations(text) == []


def test_every_finding_needs_exactly_one_row():
    findings = ["| F1 | 2 | LOST | minor | x |", "| F2 | 3 | JUMP | minor | y |"]
    assert violations(doc(findings, ["| F1 | FIX | added the definition |"])) == [
        "F2: no triage row"]
    assert violations(doc(findings[:1])) == [
        "findings exist but there is no '## Triage' section"]
    twice = ["| F1 | FIX | a |", "| F1 | FIX | b |"]
    assert "F1: triaged twice" in violations(doc(findings[:1], twice))


def test_unknown_values_and_malformed_rows_are_reported():
    assert any("want 5" in p for p in violations(doc(["| F1 | 2 | LOST | x |"])))
    text = doc(["| F1 | 2 | STYLE | major | x |"], ["| F1 | SKIP | n |"])
    problems = violations(text)
    assert "F1: unknown type 'STYLE'" in problems
    assert "F1: unknown severity 'major'" in problems
    assert "F1: unknown decision 'SKIP'" in problems


def test_headerless_findings_table_is_not_sound():
    text = "# Listener findings\n\n## Findings\n\n| F1 | 2 | WHY | blocks | x |\n"
    assert violations(text) != []


def test_wrong_triage_header_is_reported():
    text = doc(["| F1 | 2 | WHY | blocks | x |"]) + (
        "\n## Triage\n\n| ID | Verdict | Note |\n|----|---------|------|\n"
        "| F1 | FIX | added the reason |\n")
    assert any("triage table header" in p for p in violations(text))
