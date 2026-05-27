"""High-level generation and persistence orchestration for scene drafts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from .models import DraftRecord, GenerationSettings, SceneSource
from .ollama_client import OllamaClient
from .prompt_builder import build_initial_prompt, build_refinement_prompt
from .storage import next_draft_number, save_draft


def default_settings() -> GenerationSettings:
    """Return default generation settings."""

    return GenerationSettings(
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
    )


def generate_initial_draft(
    *,
    series_root: Path,
    source: SceneSource,
    settings: GenerationSettings,
    client: OllamaClient | None = None,
) -> DraftRecord:
    """Generate and persist the first or next standalone draft."""

    prompt = build_initial_prompt(source)
    return generate_and_save(
        series_root=series_root,
        source=source,
        settings=settings,
        prompt=prompt,
        user_feedback="",
        client=client,
    )


def refine_draft(
    *,
    series_root: Path,
    source: SceneSource,
    previous_draft: str,
    user_feedback: str,
    settings: GenerationSettings,
    client: OllamaClient | None = None,
) -> DraftRecord:
    """Generate and persist a refinement using the previous draft as context."""

    prompt = build_refinement_prompt(source, previous_draft, user_feedback)
    return generate_and_save(
        series_root=series_root,
        source=source,
        settings=settings,
        prompt=prompt,
        user_feedback=user_feedback,
        client=client,
    )


def generate_and_save(
    *,
    series_root: Path,
    source: SceneSource,
    settings: GenerationSettings,
    prompt: str,
    user_feedback: str,
    client: OllamaClient | None = None,
) -> DraftRecord:
    """Call Ollama, build draft metadata, and persist the result."""

    active_client = client or OllamaClient()
    response = active_client.generate(
        model=settings.model,
        prompt=prompt,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )
    record = DraftRecord(
        scene_id=source.scene_id,
        draft_number=next_draft_number(series_root, source.session_id, source.scene_id),
        model=settings.model,
        temperature=settings.temperature,
        timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
        source_hash=source.source_hash,
        editorial_hash=source.editorial_hash,
        user_feedback=user_feedback,
        prompt=prompt,
        response=response,
    )
    save_draft(series_root, source.session_id, record)
    return record
