# Comprehension gate — design

Date: 2026-11-03 · Branch: `feat/comprehension-gate` (from `origin/main`, `e18bc19`)

The base predates plugin packaging: the skill calls the `walkthrough` CLI from
PATH and has no `bin/` wrapper or setup skill. Everything below targets that
base.

## Goal

Walkthroughs pass `validate` yet are hard to follow: chapters in the wrong
order, changes described without their reason, concepts used before they are
introduced, meaningful hunks never explained. Add feedback loops that catch
these before the paid `narrate` step, borrowing the loop shapes from the
superpowers skills (inline self-review, fresh-eyes check, bounded fix wave,
rulings ledger, evidence gate) at a weight that fits a one-shot artifact.

The author of the walkthrough is the agent that implemented the branch, not a
human. It already holds the "why"; its risk is the curse of knowledge — it
cannot see what a newcomer is missing — and the temptation to dismiss
findings about its own work.

## Decisions

| Topic | Decision |
|---|---|
| Primary failure mode | Comprehension (valid but hard to follow). Style-rule lints are out of scope. |
| Placement | All loops run between `validate` and `narrate`. Nothing iterates after narration, which bills a live API. |
| Approach | Inline in `skills/walkthrough/SKILL.md`, with prompts/rules in `references/` read just-in-time. No new skill, no new CLI command. |
| Fresh eyes | One listener subagent pass, one fix wave. No second listener pass. |
| Listener inputs | Blind then reveal: the rendered markdown first, the diff second. |
| Author questions | Never routed to the human. The author agent answers "why" gaps from first-hand knowledge, then commits/PR; unanswerable ones are reported at hand-off. |
| Superpowers dependency | None. The skill stays standalone; the loops are steps inside the skill. |

Rejected: a separate `walkthrough-review` skill chained from `walkthrough`
(a third skill to keep in sync, and a cross-skill handoff is easier to skip
than an inline step); CLI-orchestrated `review`/`findings` commands (new Python
and tests for what is mostly prompt work — blindness is already guaranteed by
which file the listener receives first).

## 1. Procedure

Steps 1–8 of `SKILL.md` are unchanged, except that the dangling reference to
`examples/large.json` (the file does not exist) is removed. Steps 9 onward
become (step 9 keeps today's probe: if `walkthrough --help` fails, stop and
report that `cd cli && pip install -e .` unlocks the rest):

| Step | What happens | Loop type |
|---|---|---|
| 9. Validate | `walkthrough validate [--budget S]` with the checks in §3. Fix and rerun until exit 0; cap 3 attempts, then report remaining errors and stop. | Deterministic self-correction |
| 10. Coverage self-review | Inline checklist (§4). Every warning from step 9 is resolved here. Fix the JSON inline, then rerun `validate`. | Inline self-review |
| 11. Listener pass | Run `walkthrough markdown`. Write the kept-paths diff to `.walkthrough/review/diff.patch`. Dispatch one fresh subagent with `references/listener-prompt.md` (§2). It writes `.walkthrough/review/findings.md` and returns counts only. | Fresh eyes |
| 12. Triage + fix wave | Read `references/triage.md` (§5), mark every finding, apply one edit pass, rerun `validate` (cap 3) and `markdown`. | Bounded fix + rulings |
| 13. Hand off | `narrate`, `view`, evidence-gated report with "Calls I made" (§6). | Evidence gate |

**No subagent tool available:** skip step 11 and say so at hand-off. The
author must not substitute a self-read for the listener pass — it cannot read
its own work blind.

`.walkthrough/review/` lives under the already-ignored `.walkthrough/`.

## 2. Listener prompt — `skills/walkthrough/references/listener-prompt.md`

A template the author fills in (paths only) and dispatches to a fresh
general-purpose subagent on a mid-tier model. The subagent receives files,
never session history or the JSON plan.

Role framing:

> You are an engineer on this team. A colleague sent you a narrated
> walkthrough of their branch. You will watch it once and cannot ask them
> anything. You have not seen the code.

**Phase 1 — blind.** Read only `walkthrough.md`; open no other file. Record,
per chapter:

- `LOST` — where you could not follow, and what you would need to know.
- `JUMP` — a term, type, or function used before it is introduced.
- `WHY` — a change described without the reason, where the reason matters to
  understanding it.
- `ORDER` — a chapter that would make more sense elsewhere, and where.

**Phase 2 — reveal.** Now read `diff.patch`. Record:

- `GAP` — a meaningful change that no chapter explains. Ignore lockfiles,
  generated code, and pure renames.
- `MISMATCH` — narration claiming something its shown excerpt does not
  support.

Phase 1 findings are final once written; do not retract them after reading
the diff. A gap the diff fills for you is still a gap for the viewer.

Rules:

- Do not judge correctness or hunt bugs.
- Do not comment on wording, voice, or style.
- Each finding: chapter index (or `—` for whole-walkthrough), type, one
  sentence, severity `blocks` (a viewer would lose the thread) or `minor`
  (a viewer would pause but recover).
- Rank findings by severity. If nothing important, write
  `nothing important`.
- Write everything to `findings.md`; return only counts per type and
  severity.

## 3. `validate` additions

All messages follow the existing contract in `validate.py`: name the chapter
index or path, state the problem, state the fix.

| Check | Level | Message names |
|---|---|---|
| `files[]` entry referenced by no `chapters[].file` | warning | each path; fix: show it, name it in the incidental chapter's narration, or move it to `meta.skipped` |
| Total estimated narration (`sum(words) × MS_PER_WORD`) exceeds the budget | warning | estimate vs budget; fix: merge or cut chapters |
| `zoom` focus spans more than 20 lines | error | chapter index and span; fix: narrow it or use `show` |
| any focus spans more than 60 lines | error | chapter index and span; fix: split into a `scroll` sequence |

Span is `end − start + 1`. The checks run after anchor drift correction, so
spans and coverage reflect the corrected plan.

`validate` gains `--budget SECONDS` (integer). Default:
`clamp((meta.stats.added + meta.stats.removed) × 0.45, 60, 600)`, the same
formula as `SKILL.md`. The skill passes `--budget` through when the user
supplied one. The uncovered-file check is a warning, not an error, because
the incidental chapter may legitimately cover files without a focus.

Not added (deferred, not the pain point): hedging words, narrator mentions,
title/summary length.

## 4. Coverage self-review (step 10, inline in `SKILL.md`)

A checklist the author runs itself — no subagent:

1. Every step-9 warning is resolved: each uncovered file is shown, named in
   the incidental chapter, or moved to `meta.skipped`; an over-budget total is
   cut or merged.
2. Every significant hunk maps to a chapter, the incidental chapter, or
   `meta.skipped`.
3. Every chapter says why, not only what.
4. No chapter relies on a concept a later chapter introduces.

Fix inline; rerun `validate` once. No re-review.

## 5. Triage and fix wave — `skills/walkthrough/references/triage.md`

`SKILL.md` instructs the author to read this file immediately before
triaging. The author appends a table to `findings.md` with one row per
finding:

- `FIX` — change the plan. Answer `WHY` gaps from first-hand knowledge, then
  commit messages and the PR body. If none holds the answer, narrate only
  what the code shows and list the gap as unanswered at hand-off.
- `RULING` — keep as is: one-line reason and what it costs if wrong.
- `N/A` — the listener misread (e.g. a `GAP` already in `meta.skipped`):
  one line why.

Rules:

- Every finding gets a row. Nothing is discarded silently.
- A `blocks` finding is `FIX` unless the ruling names a concrete reason.
  "Clear enough" is not a reason.
- Budget pressure is resolved by merging or cutting, never by leaving a
  `blocks` finding unfixed.

Red flags (the file includes these as a table):

| Excuse | Reality |
|---|---|
| "The listener just lacks context" | So will the viewer. That is the finding. |
| "A viewer would figure it out" | The listener did not. Fix it or rule with a reason. |
| "Fixing it blows the budget" | Merge or cut elsewhere. |
| "It's obvious from the code" | The viewer sees the excerpt, not the code. |

Fix wave: one edit pass over `.walkthrough/walkthrough.json`, then
`walkthrough validate` (cap 3 attempts) and `walkthrough markdown`. No second listener pass;
anything still failing after the cap is reported, not looped.

## 6. Hand-off (step 13)

As today, plus:

- Report each step's exit code (`validate`, `markdown`, `narrate`, `view`).
- Report the player URL only after confirming it responds (an HTTP request
  to it returns success); otherwise report the failure.
- End with **Calls I made**: paths in `meta.skipped`, hunks merged into one
  chapter, every `RULING` row with its cost-if-wrong, and every unanswered
  `WHY`. State if the listener pass was skipped for lack of a subagent tool.
- Name `.walkthrough/review/findings.md` so the user can audit the triage.

The existing exit 3 (`narrate`) / exit 4 (`view`) handling in step 10 is
unchanged.

## 7. Files touched

- `skills/walkthrough/SKILL.md` — steps 9–13; remove `examples/large.json`.
- `skills/walkthrough/references/listener-prompt.md` — new (§2).
- `skills/walkthrough/references/triage.md` — new (§5).
- `cli/walkthrough/validate.py` — coverage, total-budget, span checks.
- `cli/walkthrough/__main__.py` — wire the checks; `--budget` option.
- `cli/tests/test_validate.py`, `cli/tests/test_live_skill.py` — tests.
- `README.md`, `CLAUDE.md` — only where they describe `validate` or the
  skill's flow.

## 8. Testing

1. **CLI (TDD).** New `test_validate.py` cases at each boundary: an uncovered
   vs covered file; total estimate at budget vs one word over; `--budget`
   override vs default formula; `zoom` span 20 vs 21; focus span 60 vs 61.
   Gate: `python -m pytest cli -q` green.
2. **Skill, structural (opt-in live test).** Extend `test_live_skill.py`:
   run with `TTS_PROVIDER=fake`; assert `.walkthrough/review/findings.md`
   exists, every finding has a triage row, and no `blocks` finding lacks
   `FIX` or a `RULING` with a reason.
3. **Skill, RED/GREEN (manual, once).** On one real branch: run the current
   skill, then dispatch the listener on its markdown and record the `blocks`
   count (RED). Run the new skill on the same branch and record the `blocks`
   findings left unfixed after triage (GREEN). Report both counts.

No test calls a paid TTS provider.
