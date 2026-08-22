"""Pydantic models for walkthrough.json — the single contract between stages."""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Action = Literal["overview", "show", "scroll", "zoom", "highlight", "closing"]
FileStatus = Literal["added", "modified", "deleted", "renamed"]

MAX_FOCUS_SPAN = 60


class Stats(BaseModel):
    files: int
    added: int
    removed: int


class Meta(BaseModel):
    repo: str
    base: str
    head: str
    base_sha: str
    head_sha: str
    title: str
    summary: str
    stats: Stats
    skipped: list[str] = Field(default_factory=list)
    generated_at: str


class FileEntry(BaseModel):
    path: str
    language: str | None = None
    status: FileStatus
    old_path: str | None = None
    before: str | None = None   # filled by CLI from base_sha
    after: str | None = None    # filled by CLI from head_sha

    @model_validator(mode="after")
    def _renamed_needs_old_path(self) -> "FileEntry":
        if self.status == "renamed" and not self.old_path:
            raise ValueError("old_path is required when status is 'renamed'")
        return self


class Focus(BaseModel):
    start: int = Field(ge=1)
    end: int = Field(ge=1)
    anchor: str

    @model_validator(mode="after")
    def _span(self) -> "Focus":
        if self.end < self.start:
            raise ValueError("focus.end must be >= focus.start")
        span = self.end - self.start + 1
        if span > MAX_FOCUS_SPAN:
            raise ValueError(f"focus span {span} exceeds {MAX_FOCUS_SPAN} lines")
        return self


class AudioRef(BaseModel):
    path: str
    duration_ms: int = Field(gt=0)


class Chapter(BaseModel):
    id: str
    title: str
    action: Action
    file: str | None = None
    focus: Focus | None = None
    narration: str
    audio: AudioRef | None = None  # filled by CLI

    @model_validator(mode="after")
    def _focus_rules(self) -> "Chapter":
        if self.action in ("overview", "closing"):
            if self.file is not None or self.focus is not None:
                raise ValueError(f"action '{self.action}' must not carry file/focus")
        else:
            if self.file is None or self.focus is None:
                raise ValueError(f"action '{self.action}' requires file and focus")
        return self


class Walkthrough(BaseModel):
    version: Literal[1]
    meta: Meta
    files: list[FileEntry]
    chapters: list[Chapter]

    @model_validator(mode="after")
    def _unique_ids_and_paths(self) -> "Walkthrough":
        errors: list[str] = []
        seen_ids: set[str] = set()
        for c in self.chapters:
            if c.id in seen_ids:
                errors.append(f"chapters[]: duplicate id '{c.id}'")
            seen_ids.add(c.id)
        seen_paths: set[str] = set()
        for f in self.files:
            if f.path in seen_paths:
                errors.append(f"files[]: duplicate path '{f.path}'")
            seen_paths.add(f.path)
        if errors:
            raise ValueError("; ".join(errors))
        return self


if __name__ == "__main__":
    print(json.dumps(Walkthrough.model_json_schema(), indent=2))
