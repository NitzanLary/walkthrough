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
- `N/A`: the listener misread, for example a `GAP` on a hunk the incidental
  chapter's narration already names. The note says what it misread. Use it
  for `minor` findings only.

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
3. Stop. There is no second listener pass. If `validate` still exits 2
   after the cap, do not narrate: hand off the remaining errors with this
   file.

## Worked example

```markdown
# Listener findings

## Findings

| ID | Chapter | Type | Severity | Finding |
|----|---------|------|----------|---------|
| F1 | 3 | WHY | blocks | Chapter 3 moves the cache into the request scope but never says why. |
| F2 | 2 | JUMP | blocks | Chapter 2 passes a TenantKey that no chapter has defined yet. |
| F3 | — | GAP | minor | The diff raises the default timeout in config/defaults.yaml and no chapter mentions it. |
| F4 | 4 | LOST | minor | Chapter 4 says the limiter drains without saying what drains it. |

## Counts

LOST 1 · JUMP 1 · WHY 1 · ORDER 0 · GAP 1 · MISMATCH 0 — blocks 2 · minor 2

## Triage

| ID | Decision | Note |
|----|----------|------|
| F1 | FIX | Chapter 3 now says a request-scoped cache cannot leak one tenant's data into another's response. |
| F2 | RULING | reason: chapter 2 shows only the call site, where TenantKey reads as an opaque ID, and moving its definition earlier would put validation before the entry point — cost if wrong: a viewer carries an undefined name for three chapters. |
| F3 | N/A | Chapter 6, the incidental chapter, already names the raised timeout default in config/defaults.yaml. |
| F4 | FIX | Chapter 4 now says each request takes one token. |
```
