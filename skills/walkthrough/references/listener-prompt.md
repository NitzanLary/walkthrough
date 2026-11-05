# Listener prompt

Replace each placeholder with the absolute path of the file listed below,
resolving it against the repository root, then send everything under the
`---` line, and nothing else, to one fresh general-purpose subagent. Do not send
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
