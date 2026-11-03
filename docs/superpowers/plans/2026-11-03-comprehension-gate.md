# Comprehension Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catch walkthroughs that pass `validate` but are hard to follow. The skill adds a coverage self-review, a blind listener-subagent pass, and a ruled triage, and new `validate` checks back them up. All of it runs before the paid `narrate` step.

**Architecture:** The CLI work is a set of new deterministic checks in `cli/walkthrough/validate.py`, wired into the `validate` command along with a `--budget` option. The skill work is prose: `SKILL.md` steps 9–13, plus two files under `skills/walkthrough/references/` that the agent reads just in time. Those files define a strict `findings.md` format. A small test-side reader (`cli/tests/findings_format.py`) enforces that format: offline against the examples in the reference files, and live against a real skill run.

**Tech Stack:** Python 3.11, Typer, Pydantic v2, pytest; Markdown skill files for Claude Code.

**Spec:** `docs/superpowers/specs/2026-11-03-comprehension-gate-design.md`

## Global Constraints

- Branch `feat/comprehension-gate`, based on `origin/main` (`e18bc19`). The skill calls the `walkthrough` CLI from PATH. There is no `bin/` wrapper and no `WT` variable.
- Run everything from the repo root (`walkthrough/`). Activate the venv first: `source venv/bin/activate`. System Python is PEP-668 locked. The venv has an editable install of `cli/`, so the `walkthrough` subprocess in tests picks up source edits.
- Gate: `python -m pytest cli -q` is green. The baseline is 77 passed, 1 skipped.
- **Never call a paid TTS provider.** Any `narrate` run, or any agent run that reaches hand-off, sets `TTS_PROVIDER=fake` in the process environment.
- Exit codes are unchanged: 0 ok, 2 validation failure, 3 provider error, 4 environment problem. Warnings exit 0.
- Every `validate` message names the chapter index (`chapters[i]`) or the path (`files[j] 'path'`), states the problem, and states the fix.
- `MS_PER_WORD = 435`. Budget default: `clamp((meta.stats.added + meta.stats.removed) × 0.45, 60, 600)` seconds. `zoom` focus at most 20 lines. Any focus at most 60 lines. Span = `end − start + 1`, checked after anchor-drift correction.
- No new skill, no new CLI command, no dependency on superpowers. Renderer untouched.
- Every commit message ends with the trailer `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

## Planning notes (where the plan refines the spec)

1. **The 60-line focus cap already exists.** `schema.py` rejects any focus over `MAX_FOCUS_SPAN = 60` at load time, with exit 2. A second check in `validate.py` would never fire. Task 1 instead appends the fix to the schema's message ("split it into a scroll sequence") and pins the 60/61 boundary with a test. Drift correction shifts `start` and `end` together, so the span is the same before and after it.
2. **`examples/small.json` would trip the new total-budget warning.** It has 170 words, about 74 s, against its own budget of `137 × 0.45 = 61.65 s`. Agents copy its shape, so Task 3 trims it to 137 words (59.6 s) and adds a test that it fits.
3. **Chapter numbering.** The markdown numbers chapters from 1 (`## 1. Overview`), while `validate` messages count from 0 (`chapters[0]`). The listener uses the markdown number, and `references/triage.md` states the mapping: chapter N is `chapters[N-1]`.
4. **One `findings.md` format, one reader.** The spec's live-test assertions need a parseable file. `references/listener-prompt.md` fixes the Findings table, and `references/triage.md` fixes the Triage table. `cli/tests/findings_format.py` reads both. It runs in two places:
   - an offline test against the worked example embedded in each reference file;
   - the opt-in live test against the real output.
5. **`N/A` is for `minor` findings only.** Spec §8 requires every `blocks` finding to be `FIX` or a `RULING` with a reason. So a `blocks` finding the listener misread becomes a `RULING` whose reason names the misread.
6. **An unanswerable `WHY` becomes a `FIX` row whose note starts `unanswered:`.** The author narrows the narration to what the code shows. Hand-off lists those rows under "Calls I made".
7. **`view` blocks while it serves.** Step 13 starts it in the background and confirms it with `curl -sf -o /dev/null http://localhost:3000`, retrying for up to 30 s. The URL is reported only if that succeeds.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `cli/walkthrough/validate.py` | New checks: `check_zoom_span`, `check_uncovered_files`, `check_total_budget`, `default_budget_s` | 1–3 |
| `cli/walkthrough/schema.py` | 60-line focus message names the fix | 1 |
| `cli/walkthrough/__main__.py` | Wire the checks; `validate --budget` | 1–3 |
| `cli/tests/test_validate.py` | Boundary tests, CLI tests, `cli_plan`/`run_validate` helpers | 1–3 |
| `cli/tests/test_schema.py` | 60/61 focus boundary | 1 |
| `skills/walkthrough/examples/small.json` | Narration trimmed to its budget | 3 |
| `README.md` | `validate [--budget S]` and what it warns on; the review step | 3, 5 |
| `cli/tests/findings_format.py` | Reader and rule checker for `findings.md` (not a test module) | 4 |
| `cli/tests/test_findings_format.py` | Offline contract tests for the format and the reference examples | 4 |
| `skills/walkthrough/references/listener-prompt.md` | Listener subagent prompt and the Findings format | 4 |
| `skills/walkthrough/references/triage.md` | Triage rules, red flags, fix wave, worked example | 4 |
| `skills/walkthrough/SKILL.md` | Steps 9–13; drop the `examples/large.json` reference | 5 |
| `cli/tests/test_live_skill.py` | Fake TTS; `findings.md` assertions | 5 |
| `CLAUDE.md` | One line on the skill's review output | 5 |

---

### Task 1: Span checks — `zoom` ≤ 20 lines; the 60-line message names the fix

**Files:**
- Modify: `cli/walkthrough/validate.py`: add `MAX_ZOOM_SPAN` and `check_zoom_span` after `check_focus_ranges`
- Modify: `cli/walkthrough/schema.py`: the `Focus._span` error message
- Modify: `cli/walkthrough/__main__.py`: the `from .validate import` line and the `validate()` body
- Test: `cli/tests/test_validate.py`, `cli/tests/test_schema.py`

**Interfaces:**
- Consumes: `Walkthrough` and `Chapter.focus` from `walkthrough.schema`; `filled_plan()` (already in `test_validate.py`); `commit_file` from `conftest`; `make_plan` from `test_schema`.
- Produces:
  - `validate.MAX_ZOOM_SPAN: int = 20`
  - `validate.check_zoom_span(wt: Walkthrough) -> list[str]`, which returns errors
  - test helpers in `test_validate.py`, used again in Tasks 2 and 3:
    - `cli_plan(repo: Path, after: str = AFTER) -> dict`
    - `run_validate(repo: Path, p: dict, *args: str) -> subprocess.CompletedProcess`
    - `LONG: str`, 30 lines reading `line 1` … `line 30`

- [ ] **Step 1: Write the failing tests**

In `cli/tests/test_validate.py`, extend the `walkthrough.validate` import to:

```python
from walkthrough.validate import (check_anchors, check_chapter_order,
                                  check_file_refs, check_focus_ranges,
                                  check_narration_budget, check_zoom_span)
```

Directly below `filled_plan()`, add the shared helpers:

```python
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
```

At the end of the file, add:

```python
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
```

In `cli/tests/test_schema.py`, after `test_focus_span_over_60_rejected`, add:

```python
def test_focus_span_60_accepted_61_names_the_fix():
    p = make_plan()
    p["chapters"][1]["action"] = "show"
    p["chapters"][1]["focus"] = {"start": 1, "end": 60, "anchor": "x"}
    Walkthrough.model_validate(p)

    p["chapters"][1]["focus"]["end"] = 61
    with pytest.raises(ValidationError, match="61 exceeds 60 lines.*scroll"):
        Walkthrough.model_validate(p)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source venv/bin/activate && python -m pytest cli/tests/test_validate.py cli/tests/test_schema.py -q`
Expected:
- `test_validate.py` fails to collect with `ImportError: cannot import name 'check_zoom_span'`.
- `test_focus_span_60_accepted_61_names_the_fix` fails because the message has no `scroll`.

- [ ] **Step 3: Implement**

In `cli/walkthrough/validate.py`, set the constants line to:

```python
DRIFT_WINDOW = 20
# A taller focus cannot fill the frame, so the shot reads as a `show`.
MAX_ZOOM_SPAN = 20
```

Then add after `check_focus_ranges`:

```python
def check_zoom_span(wt: Walkthrough) -> list[str]:
    errors = []
    for i, ch in enumerate(wt.chapters):
        if ch.action != "zoom" or ch.focus is None:
            continue
        span = ch.focus.end - ch.focus.start + 1
        if span > MAX_ZOOM_SPAN:
            errors.append(
                f"chapters[{i}] ({ch.id}): zoom focus spans {span} lines "
                f"({ch.focus.start}-{ch.focus.end}), over the {MAX_ZOOM_SPAN}-line "
                f"zoom limit. Narrow it to the lines that matter, or use 'show'.")
    return errors
```

In `cli/walkthrough/schema.py`, `Focus._span`, change the raise to:

```python
            raise ValueError(f"focus span {span} exceeds {MAX_FOCUS_SPAN} lines; "
                             f"split it into a scroll sequence")
```

In `cli/walkthrough/__main__.py`, change the import to:

```python
from .validate import (check_anchors, check_chapter_order, check_file_refs,
                       check_focus_ranges, check_narration_budget,
                       check_zoom_span)
```

In `validate()`, after `errors += check_focus_ranges(wt)`, add:

```python
        errors += check_zoom_span(wt)
```

The zoom check runs after `check_anchors`, so it measures the drift-corrected focus.

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest cli -q`
Expected: all pass (81 passed, 1 skipped). `schema.json` is unaffected, because error messages are not part of the JSON schema. `test_schema_json_in_sync_with_models` stays green.

- [ ] **Step 5: Commit**

```bash
git add cli/walkthrough/validate.py cli/walkthrough/schema.py cli/walkthrough/__main__.py cli/tests/test_validate.py cli/tests/test_schema.py
git commit -m "Reject zoom shots taller than 20 lines

The 60-line schema error now names its fix as well.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Warn on files no chapter shows

**Files:**
- Modify: `cli/walkthrough/validate.py`: add `check_uncovered_files` after `check_zoom_span`
- Modify: `cli/walkthrough/__main__.py`: import line and the `validate()` body
- Test: `cli/tests/test_validate.py`

**Interfaces:**
- Consumes: `cli_plan`, `run_validate`, and `filled_plan` from Task 1; `FileEntry` from `walkthrough.schema`.
- Produces: `validate.check_uncovered_files(wt: Walkthrough) -> list[str]`, which returns warnings.

The check is a warning, not an error. The incidental chapter may cover a file by naming it in its narration, without showing it on screen. `SKILL.md` step 10 (Task 5) treats a warning left standing that way as a call to report at hand-off.

- [ ] **Step 1: Write the failing tests**

In `cli/tests/test_validate.py`:
- Add `check_uncovered_files` to the `walkthrough.validate` import.
- Change `from walkthrough.schema import Walkthrough` to `from walkthrough.schema import FileEntry, Walkthrough`.

Then append:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cli/tests/test_validate.py -q`
Expected: collection error, `ImportError: cannot import name 'check_uncovered_files'`.

- [ ] **Step 3: Implement**

In `cli/walkthrough/validate.py`, after `check_zoom_span`:

```python
def check_uncovered_files(wt: Walkthrough) -> list[str]:
    shown = {ch.file for ch in wt.chapters if ch.file is not None}
    return [
        f"files[{j}] '{f.path}' is shown by no chapter. Show it, name it in the "
        f"incidental chapter's narration, or move it to meta.skipped."
        for j, f in enumerate(wt.files) if f.path not in shown
    ]
```

In `cli/walkthrough/__main__.py`, change the import to:

```python
from .validate import (check_anchors, check_chapter_order, check_file_refs,
                       check_focus_ranges, check_narration_budget,
                       check_uncovered_files, check_zoom_span)
```

In `validate()`, after `warnings += check_narration_budget(wt)`, add:

```python
        warnings += check_uncovered_files(wt)
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest cli -q`
Expected: all pass (83 passed, 1 skipped). Existing CLI tests still exit 0 with no new warning, because their one file is shown by chapter `c02`.

- [ ] **Step 5: Commit**

```bash
git add cli/walkthrough/validate.py cli/walkthrough/__main__.py cli/tests/test_validate.py
git commit -m "Warn when a file in the plan is shown by no chapter

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Total narration budget and `validate --budget`

**Files:**
- Modify: `cli/walkthrough/validate.py`: add budget constants, `default_budget_s`, and `check_total_budget` after `check_narration_budget`
- Modify: `cli/walkthrough/__main__.py`: import line; `validate()` gains `--budget`
- Modify: `skills/walkthrough/examples/small.json`: the six `narration` strings
- Modify: `README.md`: the Commands line, plus one paragraph on `validate`
- Test: `cli/tests/test_validate.py`

**Interfaces:**
- Consumes: `cli_plan`, `run_validate`, and `filled_plan` from Task 1; `REPO` from `test_schema`.
- Produces:
  - `validate.default_budget_s(wt: Walkthrough) -> float`: `clamp((added + removed) × 0.45, 60, 600)`
  - `validate.check_total_budget(wt: Walkthrough, budget_s: float) -> list[str]`, which returns warnings
  - CLI: `walkthrough validate [--budget SECONDS]`, where SECONDS is an integer ≥ 1

- [ ] **Step 1: Write the failing tests**

In `cli/tests/test_validate.py`:
- Add `check_total_budget` and `default_budget_s` to the `walkthrough.validate` import.
- Add `import pytest` to the imports.
- Change `from test_schema import make_plan` to `from test_schema import REPO, make_plan`.

Then append:

```python
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


@pytest.mark.parametrize("added,removed,want", [
    (4, 0, 60), (1000, 0, 450), (900, 100, 450), (2000, 0, 600)])
def test_default_budget_is_clamped_from_kept_stats(added, removed, want):
    wt = filled_plan()
    wt.meta.stats.added, wt.meta.stats.removed = added, removed
    assert default_budget_s(wt) == pytest.approx(want)


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cli/tests/test_validate.py -q`
Expected: collection error, `ImportError: cannot import name 'check_total_budget'`.

- [ ] **Step 3: Implement the check**

In `cli/walkthrough/validate.py`, below `MAX_ZOOM_SPAN`, add:

```python
# The default total budget, the same formula SKILL.md states: seconds per
# changed line in the kept diff, clamped.
BUDGET_S_PER_CHANGED_LINE = 0.45
BUDGET_MIN_S, BUDGET_MAX_S = 60, 600
```

After `check_narration_budget`, add:

```python
def default_budget_s(wt: Walkthrough) -> float:
    changed = wt.meta.stats.added + wt.meta.stats.removed
    return min(BUDGET_MAX_S, max(BUDGET_MIN_S, changed * BUDGET_S_PER_CHANGED_LINE))


def check_total_budget(wt: Walkthrough, budget_s: float) -> list[str]:
    """Warn when the whole narration will overrun the walkthrough's budget."""
    words = sum(len(ch.narration.split()) for ch in wt.chapters)
    est_ms = words * MS_PER_WORD
    if est_ms <= budget_s * 1000:
        return []
    return [
        f"narration totals {words} words, about {est_ms / 1000:.0f}s spoken, "
        f"over the {budget_s:.0f}s budget ({int(budget_s * 1000 // MS_PER_WORD)} "
        f"words). Merge repetitive chapters or cut narration."]
```

In `cli/walkthrough/__main__.py`, change the import to:

```python
from .validate import (check_anchors, check_chapter_order, check_file_refs,
                       check_focus_ranges, check_narration_budget,
                       check_total_budget, check_uncovered_files,
                       check_zoom_span, default_budget_s)
```

Replace the `validate` command's signature and the `if not errors:` block so the command reads:

```python
@app.command()
def validate(
    budget: int | None = typer.Option(
        None, "--budget", min=1,
        help="Total narration budget in seconds "
             "(default: clamp((added + removed) × 0.45, 60, 600))"),
) -> None:
    """Schema + cross-checks + anchor drift; fills files[].before/after."""
    wt = _load_plan()
    errors = fill_contents(wt, Path.cwd())
    errors += check_file_refs(wt)
    warnings: list[str] = []
    if not errors:
        warnings, anchor_errors = check_anchors(wt)
        errors += anchor_errors
        errors += check_focus_ranges(wt)
        errors += check_zoom_span(wt)
        errors += check_chapter_order(wt)
        warnings += check_narration_budget(wt)
        warnings += check_total_budget(
            wt, budget if budget is not None else default_budget_s(wt))
        warnings += check_uncovered_files(wt)
    for msg in warnings:
        typer.echo(f"warning: {msg}")
    if errors:
        _fail(errors)
    WT_JSON.write_text(wt.model_dump_json(indent=2))
    typer.echo(f"ok — {len(wt.chapters)} chapters, {len(wt.files)} files")
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest cli/tests/test_validate.py -q`
Expected: every test passes except `test_small_example_fits_its_own_budget`. That one fails with a warning like `narration totals 170 words, about 74s spoken, over the 62s budget`.

- [ ] **Step 5: Trim the example to its budget**

In `skills/walkthrough/examples/small.json`, replace each chapter's `narration` value with the text below. Change only the `narration` field. These total 137 words, about 59.6 s, under the 61.65 s budget, and every chapter stays under 57 words.

| id | new `narration` |
|---|---|
| `c01` | `This change adds per-key rate limiting to the public API. A new token-bucket module backs a request middleware that returns 429 when a key runs dry.` |
| `c02` | `TokenBucket holds a capacity, a refill rate, and a timestamp. Each take refills it by elapsed time, then spends one token if one is available.` |
| `c03` | `RateLimiter maps each API key to its own bucket, created on first sight. A lock guards the plain dict, sized for one process.` |
| `c04` | `The middleware reads the API key header and asks the limiter for a token. A rejection short-circuits with 429 and a Retry-After header.` |
| `c05` | `The tests freeze time to check refill arithmetic, exhaust a bucket to hit the 429 path, and confirm distinct keys use distinct buckets.` |
| `c06` | `Per-key limits now live in one module, wired through a single middleware and covered by time-controlled tests.` |

- [ ] **Step 6: Document `validate`**

In `README.md`, change the Commands line from ``Commands: `validate` · `markdown` ·`` to:

```markdown
Commands: `validate [--budget SECONDS]` · `markdown` ·
```

Insert this after the paragraph that ends ``holds the output path).`` and before the `narrate --dry-run` paragraph:

```markdown
`validate` checks the plan against the schema and the recorded SHAs, corrects
small anchor drift, and rejects a `zoom` taller than 20 lines (any focus over
60). It warns, still exiting 0, when a chapter's narration runs past 25 s,
when the whole narration runs past the budget (`--budget`, default
`clamp((added + removed) × 0.45, 60, 600)` seconds from `meta.stats`), and when
a file in `files[]` is shown by no chapter.
```

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest cli -q`
Expected: all pass (90 passed, 1 skipped). The count is 83 plus `test_total_budget…`, 4 parametrized default-budget cases, the CLI test, and the example test.

- [ ] **Step 8: Commit**

```bash
git add cli/walkthrough/validate.py cli/walkthrough/__main__.py cli/tests/test_validate.py skills/walkthrough/examples/small.json README.md
git commit -m "Warn when the whole narration overruns the budget

validate gains --budget. The default is the skill's formula, taken from
meta.stats. The worked example is trimmed to fit its own budget.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: The `findings.md` contract: reader, listener prompt, triage rules

**Files:**
- Create: `cli/tests/findings_format.py`. A helper module, not a test module: pytest does not collect it, because the name has no `test_` prefix.
- Create: `cli/tests/test_findings_format.py`
- Create: `skills/walkthrough/references/listener-prompt.md`
- Create: `skills/walkthrough/references/triage.md`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces, in `findings_format`, which Task 5's live test also imports:
  - `TYPES`, `SEVERITIES`, `DECISIONS: set[str]`
  - `Finding(id, chapter, type, severity, text)` and `Decision(id, decision, note)`, all `str` fields
  - `parse(text: str) -> tuple[dict[str, Finding], list[Decision], list[str]]`, returning findings by ID, triage rows, and format problems
  - `violations(text: str) -> list[str]`, returning every format and triage-rule breach; empty means sound
- Produces, for Task 5's `SKILL.md`:
  - `references/listener-prompt.md` holds the dispatch instructions above its first line that is exactly `---`. Everything below that line is the prompt. Placeholders: `{MARKDOWN}`, `{DIFF}`, `{FINDINGS}`.
  - `references/triage.md` holds the rules and the fix wave.

**The format.** The listener writes:
- `# Listener findings`
- `## Findings`: a table `| ID | Chapter | Type | Severity | Finding |`. If there are no findings, the table is empty and `nothing important` follows it.
- `## Counts`

The author appends `## Triage`, a table `| ID | Decision | Note |`. The tables' header rows are fixed. Cells never contain `|`.

- [ ] **Step 1: Write the failing tests**

Create `cli/tests/test_findings_format.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest cli/tests/test_findings_format.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'findings_format'`.

- [ ] **Step 3: Implement the reader**

Create `cli/tests/findings_format.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest cli/tests/test_findings_format.py -q`
Expected: the three reference-file tests fail with `FileNotFoundError`; the other five pass.

- [ ] **Step 5: Write the listener prompt**

Create `skills/walkthrough/references/listener-prompt.md` with exactly this content. The first line that is exactly `---` separates the dispatch notes from the prompt, so do not add another `---` line above it.

````markdown
# Listener prompt

Fill in the three absolute paths below, then send everything under the `---`
line, and nothing else, to one fresh general-purpose subagent. Do not send
session history, `walkthrough.json`, or hints about what you expect it to
find. If the tool lets you choose a model, a mid-tier one is enough.

- `{MARKDOWN}`: `.walkthrough/walkthrough.md`
- `{DIFF}`: `.walkthrough/review/diff.patch`
- `{FINDINGS}`: `.walkthrough/review/findings.md`

---

You are an engineer on this team. A colleague sent you a narrated walkthrough
of their branch. You will watch it once and cannot ask them anything. You have
not seen the code.

Your job is to find where a viewer would lose the thread. You are not
reviewing the code.

## Phase 1: blind

Read `{MARKDOWN}`. Open no other file yet. Each `## N.` heading is one
chapter; refer to chapters by that number N. Record:

- `LOST`: a chapter you could not follow, and what you would need to know.
- `JUMP`: a term, type, or function used before any chapter introduces it.
- `WHY`: a change described without its reason, where the reason matters to
  understanding it.
- `ORDER`: a chapter that would make more sense elsewhere; say where.

## Phase 2: reveal

Now read `{DIFF}`. Record:

- `GAP`: a meaningful change that no chapter explains. Ignore lockfiles,
  generated code, and pure renames.
- `MISMATCH`: narration that claims something its shown excerpt does not
  support.

Phase 1 findings are final once written. Do not retract or soften them after
reading the diff. A gap the diff fills for you is still a gap for a viewer,
who never sees the diff.

## Rules

- Do not judge correctness or hunt bugs.
- Do not comment on wording, voice, or style.
- One finding per row, in one sentence, with no `|` characters.
- Severity is `blocks` when a viewer would lose the thread and `minor` when
  a viewer would pause but recover.
- Chapter is the `## N.` number, or `—` for the walkthrough as a whole.
- IDs are `F1`, `F2`, … in table order, with `blocks` rows first.
- If nothing is worth reporting, leave the table empty and write
  `nothing important` under it.

## Output

Write `{FINDINGS}` in exactly this shape. Keep the header rows as they are:

```markdown
# Listener findings

## Findings

| ID | Chapter | Type | Severity | Finding |
|----|---------|------|----------|---------|
| F1 | 3 | WHY | blocks | Chapter 3 moves the cache into the request scope but never says why, and chapters 4 and 5 depend on that choice. |
| F2 | 2 | JUMP | minor | Chapter 2 uses "tenant key" before any chapter defines it. |

## Counts

LOST 0 · JUMP 1 · WHY 1 · ORDER 0 · GAP 0 · MISMATCH 0 — blocks 1 · minor 1
```

Then reply with only the Counts line. Do not repeat the findings in your
reply; they are in the file.
````

- [ ] **Step 6: Write the triage rules**

Create `skills/walkthrough/references/triage.md` with exactly this content:

````markdown
# Triage

Read this immediately before triaging `.walkthrough/review/findings.md`.

You built this change and you wrote its walkthrough. That is why the listener
pass exists. You cannot see what a newcomer is missing, and you will be
tempted to dismiss findings about your own work. Every finding gets a
decision you can defend in writing.

## Chapter numbers

The listener numbers chapters as the markdown does, from 1. Chapter N in a
finding is `chapters[N-1]` in `walkthrough.json`, the index `validate`
reports. `—` means the walkthrough as a whole.

## Decisions

Append a `## Triage` table to `findings.md`, with one row per finding:

- `FIX`: change the plan. The note says what changed.
- `RULING`: keep the plan as it is. The note reads
  `reason: <why> — cost if wrong: <what a viewer loses if you are mistaken>`.
- `N/A`: the listener misread, for example a `GAP` on a path already in
  `meta.skipped`. The note says what it misread. Use it for `minor` findings
  only.

If the findings table is empty (`nothing important`), there is nothing to
triage. Go on to hand-off.

## Rules

- Every finding gets exactly one row. Nothing is discarded silently.
- A `blocks` finding is `FIX` unless a `RULING` names a concrete reason.
  "Clear enough" is not a reason. A `blocks` finding the listener misread
  gets a `RULING` whose reason names the misread, never `N/A`.
- Budget pressure is resolved by merging or cutting other chapters, never by
  leaving a `blocks` finding unfixed.
- Each note is one line. It is never empty and has no `|` characters.

## Answering WHY

You are the author, so the reason is usually in what you know from building
this change. Use that first, then commit messages, then the PR body. Never
ask the user. If none of them holds the reason, narrate only what the code
shows. Mark the row `FIX` with the note `unanswered: <the question>`, and list
it at hand-off.

## Red flags

| Excuse | Reality |
|--------|---------|
| "The listener just lacks context" | So will the viewer. That is the finding. |
| "A viewer would figure it out" | The listener did not. Fix it or rule with a reason. |
| "Fixing it blows the budget" | Merge or cut elsewhere. |
| "It's obvious from the code" | The viewer sees the excerpt, not the code. |

## The fix wave

1. Apply every `FIX` in one edit pass over `.walkthrough/walkthrough.json`.
2. Rerun `walkthrough validate`, at most 3 attempts, then `walkthrough markdown`.
3. Stop. There is no second listener pass. Anything still failing after the
   cap goes into the hand-off report.

## Worked example

```markdown
# Listener findings

## Findings

| ID | Chapter | Type | Severity | Finding |
|----|---------|------|----------|---------|
| F1 | 3 | WHY | blocks | Chapter 3 moves the cache into the request scope but never says why. |
| F2 | 2 | JUMP | blocks | Chapter 2 passes a TenantKey that no chapter has defined yet. |
| F3 | — | GAP | minor | The diff changes config/defaults.yaml and no chapter mentions it. |
| F4 | 4 | LOST | minor | Chapter 4 says the limiter drains without saying what drains it. |

## Counts

LOST 1 · JUMP 1 · WHY 1 · ORDER 0 · GAP 1 · MISMATCH 0 — blocks 2 · minor 2

## Triage

| ID | Decision | Note |
|----|----------|------|
| F1 | FIX | Chapter 3 now says a request-scoped cache cannot leak one tenant's data into another's response. |
| F2 | RULING | reason: chapter 2 shows only the call site, where TenantKey reads as an opaque ID, and moving its definition earlier would put validation before the entry point — cost if wrong: a viewer carries an undefined name for three chapters. |
| F3 | N/A | config/defaults.yaml is listed in meta.skipped as a generated file. |
| F4 | FIX | Chapter 4 now says each request takes one token. |
```
````

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest cli -q`
Expected: all pass (98 passed, 1 skipped). That is 90 plus the 8 tests in `test_findings_format.py`.

- [ ] **Step 8: Commit**

```bash
git add cli/tests/findings_format.py cli/tests/test_findings_format.py skills/walkthrough/references/
git commit -m "Add the listener prompt, triage rules and findings.md contract

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: `SKILL.md` steps 9–13, live-test assertions, docs

**Files:**
- Modify: `skills/walkthrough/SKILL.md`: lines 18–19 (the examples sentence), and everything from `9. **Validate and fix.**` to the end of the file
- Modify: `cli/tests/test_live_skill.py`
- Modify: `cli/tests/test_schema.py`: one structural test
- Modify: `CLAUDE.md` line 46, `README.md` "Use" section

**Interfaces:**
- Consumes:
  - `validate --budget` from Task 3
  - `findings_format.violations` and `findings_format.parse` from Task 4
  - `references/listener-prompt.md`, which has `{MARKDOWN}`, `{DIFF}` and `{FINDINGS}` below its first `---` line, from Task 4
  - `references/triage.md` from Task 4
- Produces: the skill procedure the live test and Task 6 exercise. The output is `.walkthrough/review/diff.patch` and `.walkthrough/review/findings.md`.

- [ ] **Step 1: Write the failing structural test**

In `cli/tests/test_schema.py`, add `import re` to the imports and append:

```python
def test_skill_md_points_only_at_files_that_exist():
    skill = REPO / "skills/walkthrough"
    text = (skill / "SKILL.md").read_text()
    refs = set(re.findall(r"`((?:examples|references)/[\w.-]+)`", text))
    assert {"examples/small.json", "references/listener-prompt.md",
            "references/triage.md"} <= refs
    assert [r for r in sorted(refs) if not (skill / r).exists()] == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest cli/tests/test_schema.py -q -k points_only`
Expected: FAIL. `SKILL.md` names neither reference file yet, and it names the missing `examples/large.json`.

- [ ] **Step 3: Fix the examples sentence**

In `skills/walkthrough/SKILL.md`, replace:

```markdown
Schema: `schema.json` (next to this file). Worked examples: `examples/small.json`
(~150-line diff), `examples/large.json` (~2k-line diff). Match their shape exactly.
```

with:

```markdown
Schema: `schema.json` (next to this file). Worked example: `examples/small.json`
(~150-line diff). Match its shape exactly.
```

- [ ] **Step 4: Replace steps 9 and 10 with steps 9–13**

In `skills/walkthrough/SKILL.md`, delete everything from the line starting `9. **Validate and fix.**` to the end of the file, and put this in its place:

````markdown
9. **Validate and fix.** Probe the CLI first with `walkthrough --help`. If it is
   not on PATH, stop here and report that the plan is written and that
   `cd cli && pip install -e .` unlocks the rest; everything from here on needs
   the CLI. Otherwise run `walkthrough validate`, adding `--budget SECONDS`
   when the user passed one (without it, `validate` derives the default budget
   above from `meta.stats`). Read its errors, fix the JSON, and rerun until it
   exits 0 (exit 2 is a validation failure). Cap at 3 attempts, then report the
   remaining errors to the user and stop.

   Focus line numbers do not have to be exact. When the anchor text matches
   exactly one line within ±20 lines of `focus.start`, `validate` shifts `start`
   and `end` by that delta, prints a `warning:`, and writes the corrected plan
   back. That is the expected path, not something to pre-empt. Only two anchor
   problems are errors: an anchor found nowhere in that window (wrong text, or
   a line number off by more than 20), and an anchor matching several lines
   inside it. Both are fixed by choosing a more distinctive start line — a
   `def`, `class`, or decorator rather than a brace, a blank line, or a line
   that repeats nearby. Author anchors for distinctiveness, not for
   line-number precision.

   `validate` also rejects a `zoom` whose focus spans more than 20 lines, and
   any focus over 60; each message names the chapter and the fix. Its other
   warnings exit 0 but are not optional, and step 10 resolves every one: a
   chapter over the 25 s ceiling, narration over the total budget, and a file
   that no chapter shows.

10. **Coverage self-review.** Check the plan yourself against this list, fix
    the JSON inline, then rerun `walkthrough validate` once:
    1. Every step-9 warning is resolved. Cut a chapter over the 25 s ceiling,
       or split it into a zoom + scroll pair. Merge or cut chapters until the
       total fits the budget. For a file that no chapter shows, either show
       it, move it to `meta.skipped`, or name it in the incidental chapter's
       narration. The last option leaves that warning standing, so list the
       file under "Calls I made" at hand-off.
    2. Every significant hunk in the diff maps to a chapter, the incidental
       chapter, or `meta.skipped`.
    3. Every chapter says why the code is shaped this way, not only what it
       does.
    4. No chapter relies on a term, type, or function that only a later
       chapter introduces.

    Do not re-review after fixing; the listener pass is the next check.

11. **Listener pass.** You wrote this plan knowing the code, so you cannot see
    where a newcomer gets lost. A fresh reader can.
    1. Run `walkthrough markdown`.
    2. Remove any `findings.md` from an earlier run, then write the diff of
       the kept paths: every `files[].path`, plus `old_path` for renames.
       ```
       mkdir -p .walkthrough/review && rm -f .walkthrough/review/findings.md
       git diff <meta.base_sha> <meta.head_sha> -- <kept paths> > .walkthrough/review/diff.patch
       ```
    3. Read `references/listener-prompt.md` (next to this file). Fill in its
       three absolute paths and dispatch the prompt to one fresh
       general-purpose subagent. Send only that prompt: no session history,
       no `walkthrough.json`, no coaching.
    4. The subagent writes `.walkthrough/review/findings.md` and replies with
       counts only.

    If you have no subagent tool, skip this step and step 12, and say so at
    hand-off. Do not substitute your own read of the markdown, because you
    cannot read your own plan blind.

12. **Triage and fix.** Read `references/triage.md` now, immediately before
    triaging. Then:
    1. Append a `## Triage` table to `findings.md` with one row per finding,
       marked `FIX`, `RULING`, or `N/A` as that file defines them. A `blocks`
       finding is `FIX` unless a `RULING` names a concrete reason.
    2. Apply every `FIX` in one edit pass over `.walkthrough/walkthrough.json`.
       Answer `WHY` findings from what you know from building this change,
       then from commit messages and the PR body. Never ask the user.
    3. Rerun `walkthrough validate` (cap 3 attempts, as in step 9), then
       `walkthrough markdown`.

    This is a single wave. Do not dispatch the listener again. Whatever still
    fails after the cap is reported at hand-off, not looped on. If the
    findings table is empty (`nothing important`), there is nothing to triage.

13. **Hand off.** Run `walkthrough narrate`. Then start `walkthrough view` in
    the background, because it keeps serving until stopped. Confirm the
    player responds with `curl -sf -o /dev/null http://localhost:3000`,
    retrying for up to 30 s. Report:
    - each command's exit code: the last `validate`, `markdown`, and
      `narrate`, plus `view` if it exited, or the `curl` failure;
    - the player URL, only if `curl` succeeded;
    - the markdown path and the chapter list;
    - `.walkthrough/review/findings.md`, so the user can audit the triage;
    - **Calls I made:**
      - every path in `meta.skipped`;
      - every chapter that merges several hunks, and the pattern it names;
      - every file left unshown on purpose;
      - every `RULING` row, with its cost if wrong;
      - every `unanswered:` row;
      - whether the listener pass was skipped.

    The commands fail independently, so report what succeeded rather than only
    the last error:
    - `markdown` needs nothing beyond the validated plan.
    - `narrate` exits 3 when no TTS key is configured. The markdown is a
      complete text walkthrough on its own, so still report its path.
    - `view` exits 4 when Node is missing, the renderer has no
      `node_modules`, or port 3000 is taken; its message names the fix. Report
      the markdown path and omit the player URL.
````

- [ ] **Step 5: Run the structural test**

Run: `python -m pytest cli/tests/test_schema.py -q -k points_only`
Expected: PASS.

- [ ] **Step 6: Extend the live test**

Replace `cli/tests/test_live_skill.py` with:

```python
"""Opt-in live test: RUN_LIVE=1 LIVE_REPO=/path LIVE_BASE=main pytest -k live.
Asserts structural properties only — content quality is judged by a human
watching the result. Narration runs on the fake provider; nothing is billed."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from findings_format import parse, violations
from walkthrough import MS_PER_WORD

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to run")


def test_skill_produces_valid_plan_within_budget():
    repo_env = os.environ.get("LIVE_REPO")
    if not repo_env:
        pytest.skip("LIVE_REPO not set")
    repo = Path(repo_env)
    base = os.environ.get("LIVE_BASE", "main")
    shutil.rmtree(repo / ".walkthrough", ignore_errors=True)
    # The skill narrates at hand-off; a stale .env must not pick a paid voice.
    env = {**os.environ, "TTS_PROVIDER": "fake"}
    subprocess.run(
        ["claude", "-p", f"/walkthrough --base {base}", "--dangerously-skip-permissions"],
        cwd=repo, timeout=900, check=True, env=env)

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
    est_s = words * MS_PER_WORD / 1000  # the measured speaking rate
    assert est_s <= budget_s * 1.25, f"estimated {est_s:.0f}s vs budget {budget_s:.0f}s"

    findings_path = repo / ".walkthrough" / "review" / "findings.md"
    assert findings_path.exists(), "the listener pass wrote no findings.md"
    text = findings_path.read_text()
    assert violations(text) == []
    findings, _, _ = parse(text)
    print(f"listener findings: {len(findings)} "
          f"({sum(f.severity == 'blocks' for f in findings.values())} blocks)")
```

- [ ] **Step 7: Update the docs**

In `CLAUDE.md`, replace:

```markdown
- `skills/walkthrough/` — the planning skill. `/walkthrough` writes `.walkthrough/walkthrough.json`.
```

with:

```markdown
- `skills/walkthrough/` — the planning skill. `/walkthrough` writes `.walkthrough/walkthrough.json`,
  then has a fresh subagent read it blind and triages the result into `.walkthrough/review/findings.md`
  before narrating. Its prompts live in `skills/walkthrough/references/`.
```

In `README.md`, directly after the `walkthrough render             # → .walkthrough/out.mp4` code block, insert:

```markdown
Before narrating, the skill has a fresh subagent read the walkthrough blind,
then fixes or rules on each finding. The record lands in
`.walkthrough/review/findings.md`, and the hand-off lists every call the agent
made on your behalf.
```

- [ ] **Step 8: Run the full suite**

Run: `python -m pytest cli -q`
Expected: all pass (99 passed, 1 skipped). The live test stays skipped, and its import of `findings_format` resolves.

- [ ] **Step 9: Commit**

```bash
git add skills/walkthrough/SKILL.md cli/tests/test_live_skill.py cli/tests/test_schema.py CLAUDE.md README.md
git commit -m "Gate the walkthrough on a blind listener pass before narration

The skill now runs a coverage self-review, a fresh-eyes listener subagent,
and one ruled triage-and-fix wave. It then hands off with exit codes, a
checked player URL, and the calls it made.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: RED/GREEN comparison on a real branch (manual, once)

This task is run by the controller or the human, not by a task subagent. It needs an agent CLI that can run skills (`claude -p`, as the live test uses), a real repo, and a branch with a non-trivial diff. Use `TTS_PROVIDER=fake` throughout. If the human has not named a target, ask before starting.

**Files:** none committed. Results go into the final report.

**Interfaces:**
- Consumes:
  - the old skill at `origin/main`
  - the new skill on this branch
  - the template `references/listener-prompt.md`
  - `findings_format.parse`

- [ ] **Step 1: Set up**

```bash
export WT=/nfs/site/disks/nlary_wa/all_apollo_clones/general_ws/walkthrough
export TARGET=/path/to/target/repo   # ask the human
export BASE=main                      # the target branch's base
export TTS_PROVIDER=fake
rm -rf /tmp/wt-red && mkdir -p /tmp/wt-red
git -C "$WT" archive origin/main skills/walkthrough | tar -x -C /tmp/wt-red
ls -la "$TARGET/.claude/skills/walkthrough" 2>/dev/null   # note what was there, to restore it
```

- [ ] **Step 2: RED. Run the old skill, then the listener on its output**

```bash
cd "$TARGET"
mkdir -p .claude/skills && ln -sfn /tmp/wt-red/skills/walkthrough .claude/skills/walkthrough
rm -rf .walkthrough
claude -p "/walkthrough --base $BASE" --dangerously-skip-permissions
```

The old skill runs `walkthrough view` in the foreground, so the run can block at hand-off. RED needs only `.walkthrough/walkthrough.json`. Once that file exists and validates, interrupting the run is fine. Stop any player it left serving. Find the PID with `lsof -ti :3000`, then run `kill <PID>`. Then build the review inputs and dispatch the listener by hand:

```bash
cd "$TARGET" && walkthrough markdown && python - <<'EOF'
import json, os, subprocess
from pathlib import Path
p = json.load(open(".walkthrough/walkthrough.json"))
paths = [x for f in p["files"] for x in (f["path"], f.get("old_path")) if x]
review = Path(".walkthrough/review"); review.mkdir(parents=True, exist_ok=True)
(review / "findings.md").unlink(missing_ok=True)
(review / "diff.patch").write_text(subprocess.run(
    ["git", "diff", p["meta"]["base_sha"], p["meta"]["head_sha"], "--", *paths],
    capture_output=True, text=True, check=True).stdout)
tpl = Path(os.environ["WT"], "skills/walkthrough/references/listener-prompt.md").read_text()
root = Path(".walkthrough").resolve()
prompt = (tpl.split("\n---\n", 1)[1]
          .replace("{MARKDOWN}", str(root / "walkthrough.md"))
          .replace("{DIFF}", str(root / "review/diff.patch"))
          .replace("{FINDINGS}", str(root / "review/findings.md")))
Path("/tmp/listener-prompt.txt").write_text(prompt)
EOF
claude -p "$(cat /tmp/listener-prompt.txt)" --dangerously-skip-permissions
cp .walkthrough/review/findings.md /tmp/red-findings.md
```

Record RED, the number of `blocks` findings:

```bash
cd "$WT/cli/tests" && python -c "
from findings_format import parse
f, _, probs = parse(open('/tmp/red-findings.md').read())
print('RED blocks:', sum(x.severity == 'blocks' for x in f.values()), 'format problems:', probs)"
```

- [ ] **Step 3: GREEN. Run the new skill**

```bash
cd "$TARGET"
ln -sfn "$WT/skills/walkthrough" .claude/skills/walkthrough
rm -rf .walkthrough
claude -p "/walkthrough --base $BASE" --dangerously-skip-permissions
cp .walkthrough/review/findings.md /tmp/green-findings.md
```

Stop the player again (`lsof -ti :3000`, then `kill <PID>`). Record GREEN: the number of `blocks` findings not marked `FIX`, plus the rule check:

```bash
cd "$WT/cli/tests" && python -c "
from findings_format import parse, violations
t = open('/tmp/green-findings.md').read()
f, d, _ = parse(t); dec = {x.id: x.decision for x in d}
print('GREEN blocks found:', sum(x.severity == 'blocks' for x in f.values()))
print('GREEN blocks unfixed:', sum(x.severity == 'blocks' and dec.get(x.id) != 'FIX' for x in f.values()))
print('violations:', violations(t))"
```

- [ ] **Step 4: Restore the target and report**

Restore `$TARGET/.claude/skills/walkthrough` to what Step 1 recorded: remove the symlink if nothing was there. Delete `/tmp/wt-red`, `/tmp/listener-prompt.txt`, `/tmp/red-findings.md` and `/tmp/green-findings.md` once the counts are reported.

Report three things:
- RED blocks.
- GREEN blocks unfixed, plus GREEN blocks found.
- The GREEN hand-off's "Calls I made" section.

Expected: GREEN unfixed blocks is lower than RED blocks, and `violations` is empty. If not, treat it as a skill defect. Report it rather than tuning the prompts in this plan.
