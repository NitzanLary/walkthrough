"""Read file content pinned to the SHAs recorded at plan time — never moving refs."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .schema import Walkthrough

LANGUAGE_BY_EXT = {
    ".py": "python", ".go": "go",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".sh": "bash",
}


class GitError(Exception):
    pass


def show_file(repo: Path, sha: str, path: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), "show", f"{sha}:{path}"],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise GitError(f"git show {sha[:12]}:{path} failed: {res.stderr.strip()}")
    return res.stdout


def fill_contents(wt: Walkthrough, repo: Path) -> list[str]:
    errors: list[str] = []
    base, head = wt.meta.base_sha, wt.meta.head_sha
    for i, f in enumerate(wt.files):
        try:
            if f.status == "added":
                f.before, f.after = "", show_file(repo, head, f.path)
            elif f.status == "deleted":
                f.before, f.after = show_file(repo, base, f.path), ""
            elif f.status == "renamed":
                f.before = show_file(repo, base, f.old_path)  # old_path guaranteed by schema
                f.after = show_file(repo, head, f.path)
            else:  # modified
                f.before = show_file(repo, base, f.path)
                f.after = show_file(repo, head, f.path)
        except GitError as e:
            errors.append(f"files[{i}] ({f.path}): {e}")
            continue
        if f.language is None:
            f.language = LANGUAGE_BY_EXT.get(Path(f.path).suffix)
    return errors
