"""Data models for iterative local scene editing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SceneSource:
    """Inputs used to generate or refine one scene draft."""

    series_name: str
    session_id: str
    scene_id: str
    screenplay_path: Path
    notes_path: Path
    annotated_path: Path | None
    screenplay_markdown: str
    editorial_notes_markdown: str
    annotated_json: str
    source_hash: str
    editorial_hash: str


@dataclass(frozen=True)
class DraftRecord:
    """Persisted metadata for one generated scene draft."""

    scene_id: str
    draft_number: int
    model: str
    temperature: float
    timestamp: str
    source_hash: str
    editorial_hash: str
    user_feedback: str
    prompt: str
    response: str


@dataclass(frozen=True)
class GenerationSettings:
    """LLM generation settings."""

    model: str
    temperature: float
    max_tokens: int
