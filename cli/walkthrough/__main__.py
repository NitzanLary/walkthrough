import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from pydantic import ValidationError

from . import WT_JSON
from .git import fill_contents
from .markdown import render_markdown
from .schema import Walkthrough
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


if __name__ == "__main__":
    app()
