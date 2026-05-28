"""Data models for storyboard breakdown generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StoryboardSource:
    """Inputs used to generate one storyboard breakdown."""

    series_name: str
    session_id: str
    scene_id: str
    final_screenplay_path: Path
    final_screenplay_markdown: str
    source_hash: str


@dataclass(frozen=True)
class StoryboardShot:
    """One audiovisual storyboard shot."""

    shot_id: int
    shot_type: str
    camera_motion: str
    location: str
    time_of_day: str
    description: str
    mood: str
    lighting: str
    focus_subject: str
    visual_elements: list[str] = field(default_factory=list)
    duration_estimate_seconds: int = 4


@dataclass(frozen=True)
class StoryboardRecord:
    """Persisted storyboard generation result."""

    scene_id: str
    model: str
    temperature: float
    timestamp: str
    source_hash: str
    prompt: str
    prompt_version: str
    source_screenplay: str
    shots: list[StoryboardShot]


@dataclass(frozen=True)
class StoryboardSettings:
    """LLM generation settings for storyboard breakdown."""

    model: str
    temperature: float
    max_tokens: int
