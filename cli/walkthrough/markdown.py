"""Render the validated plan as an ordered markdown walkthrough — the zero-
dependency reading arm for the day-3 ordering gate and the evaluation."""
from __future__ import annotations

from .schema import Walkthrough
from .validate import content_side, _file_by_path


def render_markdown(wt: Walkthrough) -> str:
    m = wt.meta
    parts = [
        f"# {m.title}", "", m.summary, "",
        f"`{m.base}...{m.head}` — {m.stats.files} files, "
        f"+{m.stats.added} −{m.stats.removed}", "",
    ]
    for i, ch in enumerate(wt.chapters, 1):
        parts += [f"## {i}. {ch.title}", "", ch.narration, ""]
        if ch.focus is not None:
            f = _file_by_path(wt, ch.file)
            lines = content_side(f).splitlines()
            excerpt = lines[ch.focus.start - 1: ch.focus.end]
            parts += [f"`{ch.file}:{ch.focus.start}-{ch.focus.end}`", "",
                      f"```{f.language or ''}", *excerpt, "```", ""]
    return "\n".join(parts).rstrip("\n") + "\n"
