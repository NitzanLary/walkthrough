import json
import os
import shutil as _shutil
import subprocess
import threading
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
from .narrator.base import MissingKeyError, RateLimited, get_narrator
from .schema import AudioRef, Walkthrough
from .stage import ToolingMissing, require_node, stage_assets
from .validate import (check_anchors, check_chapter_order, check_file_refs,
                       check_focus_ranges)

app = typer.Typer(add_completion=False, no_args_is_help=True)

# Rate-limit waits burn attempts too, so leave room for a few before giving up.
_MAX_ATTEMPTS = 5


# dotenv's own discovery walks up from the installed package. For an editable
# or out-of-tree install that is a different tree than the repository being
# explained, so its .env is never found — look where the user is instead.
_ENV_PATHS: list[Path] = []


def _repo_root(start: Path) -> Path | None:
    res = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    return Path(res.stdout.strip()) if res.returncode == 0 else None


def _env_report() -> str:
    return ", ".join(f"{p}{'' if p.is_file() else ' (not found)'}" for p in _ENV_PATHS)


@app.callback()
def _init(
    env_file: Path | None = typer.Option(
        None, "--env-file", exists=True, dir_okay=False,
        help="Read environment from this file instead of the discovered .env",
    ),
) -> None:
    cwd = Path.cwd()
    if env_file is not None:
        _ENV_PATHS.append(env_file)
    else:
        _ENV_PATHS.append(cwd / ".env")
        root = _repo_root(cwd)
        if root is not None and root != cwd:
            _ENV_PATHS.append(root / ".env")
    for p in _ENV_PATHS:
        load_dotenv(p, override=False)  # already exported in the shell wins


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
    jobs: int = typer.Option(2, "-j", "--jobs", help="Parallel synthesis pool"),
) -> None:
    """Synthesize narration; fills chapters[].audio."""
    wt = _load_validated()
    # A 429 flips the whole run to serial rather than retrying into the same
    # wall: the provider is rejecting the concurrency, not the request.
    _serialized = threading.Event()
    _serial_lock = threading.Lock()
    try:
        narrator = get_narrator()
    except MissingKeyError as e:
        typer.echo(f"error: {e} — checked {_env_report()}", err=True)
        raise typer.Exit(3)
    except ValueError as e:
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
        for attempt in range(_MAX_ATTEMPTS):
            try:
                if _serialized.is_set():
                    # A 429 already told us the pace is wrong: one at a time.
                    with _serial_lock:
                        clip = narrator.synthesize(ch.narration, out,
                                                   previous_text=prev_text,
                                                   next_text=next_text)
                else:
                    clip = narrator.synthesize(ch.narration, out,
                                               previous_text=prev_text,
                                               next_text=next_text)
                break
            except RateLimited as e:
                last_err = e
                if not _serialized.is_set():
                    _serialized.set()
                    typer.echo("rate limited by provider — continuing one at a time",
                               err=True)
                time.sleep(e.retry_after if e.retry_after is not None else 2 ** attempt)
            except Exception as e:
                last_err = e
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(2 ** attempt)
        else:
            raise RuntimeError(
                f"chapter {ch.id}: synthesis failed after {_MAX_ATTEMPTS} attempts: {last_err}")
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


def _staged_renderer() -> Path:
    wt = _load_validated()
    if any(ch.audio is None for ch in wt.chapters):
        _fail(["chapters have no audio — run `walkthrough narrate` first"])
    try:
        require_node()
    except ToolingMissing as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(4)
    rd = stage_assets()
    if not (rd / "node_modules").exists():
        typer.echo(f"error: renderer dependencies missing — run `npm install` in {rd}",
                   err=True)
        raise typer.Exit(4)
    return rd


@app.command()
def view() -> None:
    """Stage assets and serve the player page on http://localhost:3000."""
    rd = _staged_renderer()
    typer.echo("player: http://localhost:3000")
    subprocess.run(["npm", "run", "view"], cwd=rd)


@app.command()
def studio() -> None:
    """Stage assets and launch Remotion Studio (dev only)."""
    rd = _staged_renderer()
    subprocess.run(["npx", "remotion", "studio"], cwd=rd)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    return True


def _claim_output(final: Path) -> Path:
    """Take the lock on `final`, refusing to start if a live render holds it.

    Two renders writing one path interleave into a file that looks valid and
    is not, so the second one must not start rather than lose the race.
    """
    lock = final.with_name(final.name + ".lock")
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return lock
        except FileExistsError:
            try:
                holder = int(lock.read_text().strip())
            except (ValueError, OSError):
                holder = None
            if holder is not None and holder != os.getpid() and _pid_alive(holder):
                typer.echo(f"error: another render (pid {holder}) is writing {final} — "
                           f"wait for it, or use --out to write elsewhere", err=True)
                raise typer.Exit(4)
            lock.unlink(missing_ok=True)  # stale: owner died without cleaning up
    raise typer.Exit(4)


@app.command()
def render(out: Path = typer.Option(Path(".walkthrough/out.mp4"), "--out")) -> None:
    """Stage assets and render the MP4."""
    rd = _staged_renderer()
    final = out.resolve()
    final.parent.mkdir(parents=True, exist_ok=True)
    lock = _claim_output(final)
    # Render beside the target and move it into place only on success, so a
    # failed or killed render leaves the previous MP4 intact.
    tmp = final.with_name(f".{final.stem}.{os.getpid()}.tmp{final.suffix}")
    try:
        res = subprocess.run(
            ["npx", "remotion", "render", "Walkthrough", str(tmp)], cwd=rd)
        if res.returncode == 0:
            tmp.replace(final)
            typer.echo(str(final))
    finally:
        tmp.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    raise typer.Exit(res.returncode)


@app.command()
def clean() -> None:
    """Delete .walkthrough/."""
    import shutil as sh
    sh.rmtree(WT_JSON.parent, ignore_errors=True)
    typer.echo("removed .walkthrough/")


if __name__ == "__main__":
    app()
