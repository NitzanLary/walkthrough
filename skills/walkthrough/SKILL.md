---
name: walkthrough
description: Plan a narrated, ordered walkthrough of the current branch's diff, write .walkthrough/walkthrough.json, and produce the markdown/audio/player outputs via the walkthrough CLI. Use when the user runs /walkthrough or asks for a narrated code walkthrough of a branch.
---

# Narrated code walkthrough

You are a senior engineer walking a teammate through this branch. Explain what
the change does and why it is shaped this way. Do not evaluate correctness, do
not hunt bugs, do not reassure.

**Invocation:** `/walkthrough [--base REF] [--budget SECONDS]`
`base` defaults to `main`. `budget` defaults to `clamp(changed_lines * 0.45, 60, 600)`
seconds, where `changed_lines` = added + removed from `git diff <base>...HEAD --stat`.

Schema: `schema.json` (next to this file). Worked examples: `examples/small.json`
(~150-line diff), `examples/large.json` (~2k-line diff). Match their shape exactly.

## Procedure

1. **Pin the snapshot.** Run `git status --porcelain`. If any file touched by
   the diff is dirty, STOP and ask the user to commit first. Record
   `git merge-base <base> HEAD` as `meta.base_sha` and `git rev-parse HEAD` as
   `meta.head_sha`. Ensure `.walkthrough/` is ignored (add it to
   `.git/info/exclude` if not).

2. **Gather context.** Run `git diff <base>...HEAD --stat`, the full diff, and
   `git log <base>..HEAD` for commit messages. If a PR exists, read
   `gh pr view --json body` (ignore failures). Read every touched file in full.
   Grep for callers, implemented interfaces, and tests when it helps explain
   *why*. If this session built the feature, prefer your first-hand knowledge of
   intent and trade-offs over the commit history.

3. **Filter noise.** Exclude lockfiles, generated code, vendored/minified files,
   binaries, whitespace-only changes, and anything matched by a
   `.walkthroughignore` file in the repo root (gitignore syntax). List every
   excluded path in `meta.skipped`.

4. **Order chapters** by this priority:
   1. Intent and entry point — what triggered the change; the public surface that is hit
   2. Data types, schemas, migrations, config shape
   3. Core logic, in call order
   4. Wiring: DI, routes, CLI flags, feature flags
   5. Tests, grouped; describe what they assert, not line by line
   6. Incidental changes (renames, cleanup) as one combined chapter

5. **Compress to the budget.** Estimate ~2.3 narrated words per second (435 ms
   per word — the measured voice, which runs slower than the nominal rate). Merge
   repetitive hunks into one chapter and name the pattern. Never narrate line by
   line; explain purpose, inputs, outputs, side effects.

6. **Camera.** `overview` first, `closing` last. `show` on first visit to a
   file; `zoom` for the 3–5 most important regions; `scroll` for sequential
   movement within a file; `highlight` for quick callbacks. Focus span ≤ 60
   lines — split if larger, and ≤ 20 lines for a `zoom`: a taller focus cannot
   fill the frame, so the shot reads as a `show`. Keep any single chapter's
   narration ≤ ~25 s — at 2.3 words/second that is ≤ 57 words, counted; split
   longer explanations into a zoom + scroll sequence rather than one static shot.

7. **Voice.** Third person ("the change adds…", "this function…"). Declarative.
   No hedging words (probably, seems, might, appears). No filler. Never mention
   the narrator, the tool, or the agent. 1–5 sentences per chapter, within the
   ≤ 57-word chapter ceiling from step 6.

8. **Write `.walkthrough/walkthrough.json`** conforming to the schema.
   - `focus.start`/`end` are 1-based inclusive, in *after* coordinates
     (*before* coordinates for deleted files).
   - For every `focus`, set `anchor` to the verbatim text of line `start` —
     copy it from the file with the Read tool, do not retype it.
   - Do NOT include `files[].before/after` or `chapters[].audio`; the CLI fills those.
   - `files[].old_path` is required when `status` is `renamed`.

9. **Validate and fix.** Run `walkthrough validate`. Read its errors, fix the
   JSON, rerun until it exits 0 with no warnings. Anchor drift is auto-corrected
   with a warning; a narration-budget warning names a chapter to cut or split and
   is not optional. Anchor ambiguity is an error — fix it by choosing a more
   distinctive focus start line. Cap at 3 attempts, then report the remaining
   errors to the user.

10. **Hand off.** Run `walkthrough markdown`, then `walkthrough narrate`, then
    `walkthrough view`. Report the player URL, the markdown path, and the
    chapter list. If narrate fails for lack of a TTS key, still report the
    markdown path — it is a complete text walkthrough on its own.
