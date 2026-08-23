# CLAUDE.md

Behavioral guidelines plus the project facts that are easy to get wrong here.

Sections 1–4 adapt [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills),
derived from Andrej Karpathy's observations on LLM coding pitfalls.

**Tradeoff:** these bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think before coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly. If uncertain, ask.
- If multiple readings exist, present them — don't pick one silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop and name what's confusing.

## 2. Simplicity first

**The minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked, no abstractions for single-use code.
- No configurability nobody requested, no error handling for impossible states.
- If 200 lines could be 50, rewrite it.

## 3. Surgical changes

**Touch only what you must. Clean up only your own mess.**

- Don't improve adjacent code, comments, or formatting; match existing style.
- Remove imports and helpers *your* change orphaned. Leave pre-existing dead code alone — mention it instead.
- Every changed line should trace to the request.

## 4. Goal-driven execution

**Define success criteria, then loop until verified.**

Turn tasks into checks: "fix the bug" → "write a test that reproduces it, then make it pass".
Verify by running the thing, not by reasoning about it — see the camera note below for why.

---

## The project

- `skills/walkthrough/` — the planning skill. `/walkthrough` writes `.walkthrough/walkthrough.json`.
- `cli/` — the `walkthrough` CLI: `validate`, `markdown`, `narrate`, `view`, `studio`, `render`, `clean`.
  Exit codes: 0 ok, 2 validation failure, 3 provider error, 4 tooling missing.
- `renderer/` — Remotion 4.0.515 (zod pinned to 4.4.3 to match). Camera math in `src/lib/timeline.ts`.

## Running things

```bash
source venv/bin/activate        # system python is PEP-668 locked
python -m pytest cli -q         # 42 tests + 1 opt-in live test

cd renderer
npx vitest run
npx tsc --noEmit                # MANDATORY — see below
```

**`npx tsc --noEmit` is not optional for renderer changes.** Vitest does not typecheck, and a
type error once shipped a Critical bug where dead code silently disabled the focus highlight.

There is no system `ffmpeg`/`ffprobe` — use `npx remotion ffprobe` / `npx remotion ffmpeg` from `renderer/`.

## Narration costs real money

`narrate` with `TTS_PROVIDER=elevenlabs` or `openai` bills a live API. **Never run it unless the
user has asked for it in this session.** Use `TTS_PROVIDER=fake` for any pipeline work — it
produces realistic timings without spending.

- ElevenLabs 429s at the default `-j 4`. Use `-j 1`.
- Never print or log API keys. `.env` is gitignored; keep it that way.
- Cached clips are keyed by provider, model, voice, and stitch context, so a failed run doesn't re-bill what already succeeded.

## Camera invariants

In `renderer/src/lib/timeline.ts`, these hold together and break loudly when nudged:

- `CODE_VIEW_H` must stay a whole multiple of `LINE_H`, scale must snap to a whole row count,
  and `y` must snap to the row grid. Drop any one and rows get sliced through the glyphs at the edges.
- Zoom is capped by focus *height* and by row *width* — the gutter scales with the text, so the
  constraint is `scale * (GUTTER_W + chars * CHAR_W) <= CODE_VIEW_W`.
- The width cap steps aside when it can't be satisfied at scale 1; a line too long to ever fit
  shouldn't deny every other line its framing.

**Verify camera changes by rendering, not by reasoning:**

```bash
npx remotion still src/index.ts Walkthrough /tmp/f.png --frame=N
```

Both camera bugs found in this repo looked fine in the code and were obvious in a still.

## Renders

A full render is ~13k frames and ~20 minutes. `render` writes `.walkthrough/out.mp4` with no
lock, so run one at a time — two concurrent renders corrupt the output. Kill renders by PID;
`pkill -f remotion` has silently failed here and let a stale render finish over a live one.

## Repo hygiene

`.walkthrough/`, `.env`, `.claude/`, `venv/`, and `node_modules/` are ignored. Don't commit
generated artifacts (audio, MP4s, staged renderer assets).

---

**These guidelines are working if:** diffs contain only what was asked for, camera changes are
verified with a rendered frame before they're claimed to work, and no paid API is called without
the user asking first.
