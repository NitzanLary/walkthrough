import json
import shutil as _shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import typer
from dotenv import load_dotenv
from pydantic import ValidationError

from . import AUDIO_DIR, WT_JSON
from .git import fill_contents
from .markdown import render_markdown
from .narrator import cache as audio_cache
from .narrator.base import MissingKeyError, get_narrator
from .schema import AudioRef, Walkthrough
from .validate import (check_anchors, check_chapter_order, check_file_refs,
                       check_focus_ranges)

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def _init() -> None:
    load_dotenv()


def _fail(errors: list[str]) -> None:
    for i, msg in enumerate(errors, 1):
        typer.echo(f"{i}. {msg}", err=True)
    raise typer.Exit(2)


def _load_plan() -> Walkthrough:
    if not WT_JSON.exists():
        _fail([f"{WT_JSON} not found — run the /walkthrough skill first"])
    try:
        data = json.loads(WT_JSON.read_text())
    except json.JSONDecodeError as e:
        _fail([f"{WT_JSON} is not valid JSON: {e}"])
    try:
        return Walkthrough.model_validate(data)
    except ValidationError as e:
        _fail([f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
               for err in e.errors()])


@app.command()
def validate() -> None:
    """Schema + cross-checks + anchor drift; fills files[].before/after."""
    wt = _load_plan()
    errors = fill_contents(wt, Path.cwd())
    errors += check_file_refs(wt)
    warnings: list[str] = []
    if not errors:
        warnings, anchor_errors = check_anchors(wt)
        errors += anchor_errors
        errors += check_focus_ranges(wt)
        errors += check_chapter_order(wt)
    for msg in warnings:
        typer.echo(f"warning: {msg}")
    if errors:
        _fail(errors)
    WT_JSON.write_text(wt.model_dump_json(indent=2))
    typer.echo(f"ok — {len(wt.chapters)} chapters, {len(wt.files)} files")


def _load_validated() -> Walkthrough:
    wt = _load_plan()
    for ch in wt.chapters:
        if ch.file is not None:
            f = next((x for x in wt.files if x.path == ch.file), None)
            if f is None or f.after is None:
                _fail(["plan has no file content — run `walkthrough validate` first"])
    return wt


@app.command()
def markdown() -> None:
    """Render the validated plan as .walkthrough/walkthrough.md."""
    wt = _load_validated()
    out = WT_JSON.parent / "walkthrough.md"
    out.write_text(render_markdown(wt))
    typer.echo(str(out))


@app.command()
def narrate(
    no_cache: bool = typer.Option(False, "--no-cache", help="Force re-synthesis"),
    jobs: int = typer.Option(4, "-j", "--jobs", help="Parallel synthesis pool"),
) -> None:
    """Synthesize narration; fills chapters[].audio."""
    load_dotenv()  # the README promises TTS_* via .env
    wt = _load_validated()
    try:
        narrator = get_narrator()
    except (MissingKeyError, ValueError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(3)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    cached_count = 0
    # Request-stitching context: neighbors' narration keeps tone continuous.
    stitch = {
        ch.id: (wt.chapters[i - 1].narration if i > 0 else "",
                wt.chapters[i + 1].narration if i + 1 < len(wt.chapters) else "")
        for i, ch in enumerate(wt.chapters)
    }

    def one(ch) -> tuple[str, AudioRef, bool]:
        out = AUDIO_DIR / f"{ch.id}.mp3"
        prev_text, next_text = stitch[ch.id]
        key = audio_cache.cache_key(narrator.provider, narrator.model,
                                    narrator.voice_id, ch.narration,
                                    previous_text=prev_text, next_text=next_text)
        if not no_cache and (hit := audio_cache.lookup(key)) is not None:
            _shutil.copy2(hit.path, out)
            return ch.id, AudioRef(path=f"audio/{ch.id}.mp3",
                                   duration_ms=hit.duration_ms), True
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                clip = narrator.synthesize(ch.narration, out,
                                           previous_text=prev_text,
                                           next_text=next_text)
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"chapter {ch.id}: synthesis failed after 3 attempts: {last_err}")
        audio_cache.store(key, clip.path, clip.duration_ms)
        return ch.id, AudioRef(path=f"audio/{ch.id}.mp3",
                               duration_ms=clip.duration_ms), False

    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(one, wt.chapters))
    except RuntimeError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(3)

    by_id = {r[0]: r for r in results}
    for ch in wt.chapters:
        _, ref, was_cached = by_id[ch.id]
        ch.audio = ref
        cached_count += was_cached
    WT_JSON.write_text(wt.model_dump_json(indent=2))
    typer.echo(f"{len(results)}/{len(results)} clips, {cached_count} cached")


if __name__ == "__main__":
    app()
