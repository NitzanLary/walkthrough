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

It is read from the working directory, then the repository root — wherever the
CLI itself is installed. `--env-file PATH` overrides both; anything already
exported in the shell wins over all of them.

## Use

    # inside Claude Code, ideally the session that built the feature
    /walkthrough --base main

    # later, from a shell
    walkthrough render             # → .walkthrough/out.mp4

Commands: `validate` · `markdown` ·
`narrate [--dry-run] [--check] [--no-cache] [-j N]` ·
`view` · `studio` · `render [--out PATH]` · `clean`.
Exit codes: 0 ok, 2 validation failure, 3 provider error, 4 environment
problem (tooling missing, or another render already holds the output path).

`narrate --dry-run` prints the provider, model, voice, chapter and character
counts, cache hits and estimated narration length without calling the API;
`narrate --check` synthesizes one short sample to prove the key, model and voice
work. A run then reports one line per chapter and a summary splitting cached,
synthesized, retried and failed clips.

`narrate` synthesizes 2 chapters at a time; a 429 from the provider drops the
run to one at a time and honors `Retry-After` rather than failing the chapter.
Each finished chapter is checkpointed into `walkthrough.json`, so an interrupted
or partly failed run keeps what landed and the rerun pays only for the rest.
`render` writes to a temp file and moves it into place only on success, so a
failed or interrupted render leaves the previous MP4 intact.

Artifacts land in `./.walkthrough/` (add it to your repo's ignores).
Audio is cached at `~/.cache/walkthrough/audio/` keyed by provider, model,
voice, and the narration text with its stitch context — reruns pay only for
changed narration (a chapter also re-synthesizes when a neighbor's text
changes, since request stitching makes its audio depend on them).
