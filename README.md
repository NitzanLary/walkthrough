# walkthrough

Narrated code walkthroughs planned by the coding agent that wrote the change.

## Install

    cd cli && pip install -e .
    cd renderer && npm install

Copy `skills/walkthrough/` into your repo's `.claude/skills/` (or symlink).
Create `.env` in the repo you review:

    TTS_PROVIDER=elevenlabs        # elevenlabs | openai | fake
    TTS_API_KEY=...                # or ELEVENLABS_API_KEY / OPENAI_API_KEY
    # optional overrides (defaults: eleven_multilingual_v2, George):
    # TTS_MODEL=eleven_multilingual_v2
    # TTS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb

## Use

    # inside Claude Code, ideally the session that built the feature
    /walkthrough --base main

    # later, from a shell
    walkthrough render             # → .walkthrough/out.mp4

Commands: `validate` · `markdown` · `narrate [--no-cache] [-j N]` · `view` ·
`studio` · `render [--out PATH]` · `clean`.
Exit codes: 0 ok, 2 validation failure, 3 provider error, 4 tooling missing.

Artifacts land in `./.walkthrough/` (add it to your repo's ignores).
Audio is cached at `~/.cache/walkthrough/audio/` keyed by provider, model,
voice, and the narration text with its stitch context — reruns pay only for
changed narration (a chapter also re-synthesizes when a neighbor's text
changes, since request stitching makes its audio depend on them).
