"""Data models for visual bible generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class VisualBibleSource:
    """Inputs used to generate a session visual bible."""

    series_name: str
    session_id: str
    final_screenplay_paths: list[Path]
    storyboard_paths: list[Path]
    final_screenplay_markdown: str
    storyboard_json_text: str
    screenplay_hash: str
    storyboard_hash: str


@dataclass(frozen=True)
class VisualBibleSettings:
    """LLM generation settings for visual bible generation."""

    model: str
    temperature: float
    max_tokens: int


@dataclass(frozen=True)
class CharacterVisualProfile:
    """Reusable visual profile for one recurring character."""

    character_id: str
    appearance: dict[str, str] = field(default_factory=dict)
    behavioral_visuals: list[str] = field(default_factory=list)
    camera_treatment: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class EnvironmentRule:
    """Reusable visual rules for one environment or location."""

    location: str
    architecture: str = ""
    weather: str = ""
    street_density: str = ""
    texture: list[str] = field(default_factory=list)
    lighting: str = ""


@dataclass(frozen=True)
class CinematographyRules:
    """Series-level cinematography guidance."""

    camera_language: dict[str, object] = field(default_factory=dict)
    lighting: dict[str, object] = field(default_factory=dict)
    color_grading: dict[str, object] = field(default_factory=dict)
    composition: dict[str, object] = field(default_factory=dict)
    lenses: dict[str, object] = field(default_factory=dict)
    texture: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SeriesVisualIdentity:
    """Top-level visual identity for future image stages."""

    references: list[str] = field(default_factory=list)
    visual_keywords: list[str] = field(default_factory=list)
    visual_rules: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VisualBibleRecord:
    """Persisted visual bible generation result."""

    session_id: str
    model: str
    temperature: float
    timestamp: str
    screenplay_hash: str
    storyboard_hash: str
    prompt: str
    prompt_version: str
    source_screenplay: str
    source_storyboard: str
    characters: list[CharacterVisualProfile]
    environments: list[EnvironmentRule]
    cinematography: CinematographyRules
    series_visual_identity: SeriesVisualIdentity
