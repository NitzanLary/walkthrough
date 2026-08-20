"""Content-dependent checks. Errors are specific and actionable: the agent reads
them to self-correct, so every message names the chapter index and the fix."""
from __future__ import annotations

from .schema import FileEntry, Walkthrough

DRIFT_WINDOW = 20


def content_side(f: FileEntry) -> str:
    """Focus coordinates live in `before` for deleted files, `after` otherwise."""
    text = f.before if f.status == "deleted" else f.after
    return text or ""


def _file_by_path(wt: Walkthrough, path: str) -> FileEntry | None:
    return next((f for f in wt.files if f.path == path), None)


def check_file_refs(wt: Walkthrough) -> list[str]:
    errors = []
    for i, ch in enumerate(wt.chapters):
        if ch.file is not None and _file_by_path(wt, ch.file) is None:
            errors.append(
                f"chapters[{i}].file '{ch.file}' is not listed in files[]")
    return errors


def check_anchors(wt: Walkthrough) -> tuple[list[str], list[str]]:
    warnings, errors = [], []
    for i, ch in enumerate(wt.chapters):
        if ch.focus is None:
            continue
        f = _file_by_path(wt, ch.file)
        if f is None:
            continue  # reported by check_file_refs
        lines = content_side(f).splitlines()
        want = ch.focus.anchor.strip()
        idx = ch.focus.start - 1
        if 0 <= idx < len(lines) and lines[idx].strip() == want:
            continue
        lo, hi = max(0, idx - DRIFT_WINDOW), min(len(lines), idx + DRIFT_WINDOW + 1)
        hits = [n for n in range(lo, hi) if lines[n].strip() == want]
        if len(hits) == 1:
            delta = hits[0] - idx
            ch.focus.start += delta
            ch.focus.end += delta
            warnings.append(
                f"chapters[{i}]: anchor drift corrected by {delta:+d} "
                f"(focus now {ch.focus.start}-{ch.focus.end})")
        elif not hits:
            errors.append(
                f"chapters[{i}]: anchor {want!r} not found within "
                f"±{DRIFT_WINDOW} lines of {ch.file}:{ch.focus.start}")
        else:
            candidates = ", ".join(str(h + 1) for h in hits)
            errors.append(
                f"chapters[{i}]: anchor {want!r} is ambiguous in {ch.file}; "
                f"candidate lines: {candidates}. Choose a more distinctive focus start.")
    return warnings, errors


def check_focus_ranges(wt: Walkthrough) -> list[str]:
    errors = []
    for i, ch in enumerate(wt.chapters):
        if ch.focus is None:
            continue
        f = _file_by_path(wt, ch.file)
        if f is None:
            continue
        n = len(content_side(f).splitlines())
        if ch.focus.end > n:
            errors.append(
                f"chapters[{i}].focus.end ({ch.focus.end}) exceeds "
                f"line count of {ch.file} ({n})")
    return errors


def check_chapter_order(wt: Walkthrough) -> list[str]:
    errors = []
    if not wt.chapters or wt.chapters[0].action != "overview":
        errors.append("chapters[0].action must be 'overview'")
    if not wt.chapters or wt.chapters[-1].action != "closing":
        errors.append(f"chapters[{max(len(wt.chapters) - 1, 0)}].action must be 'closing'")
    return errors
