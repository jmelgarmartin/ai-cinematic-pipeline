"""High-level generation and persistence orchestration for scene drafts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from .config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from .models import DraftRecord, GenerationSettings, SceneSource
from .ollama_client import OllamaClient
from .prompt_builder import PROMPT_VERSION, build_initial_prompt, build_refinement_prompt
from .storage import next_draft_number, save_draft


VALID_SCENE_START_PATTERN = re.compile(
    r"(?im)^\s*(?:#\s*)?(?:ESCENA\b|INT\.|EXT\.|INT/EXT\.|INT\.?/EXT\.?|##\s+INT\.|##\s+EXT\.)"
)
CHATBOT_PREFIX_PATTERN = re.compile(
    r"(?is)^\s*(?:okay[,\s]|let's\b|first[,\s]|i need to\b|the user\b|we need to\b|here is\b|claro[,\s]|voy a\b|a continuacion\b)"
)
THINK_BLOCK_PATTERN = re.compile(r"(?is)^\s*<think>.*?</think>\s*")
META_LINE_PATTERNS = (
    re.compile(r"(?is)^\s*okay[,\s].*?(?=\n\s*(?:#\s*)?(?:ESCENA\b|INT\.|EXT\.|##\s+INT\.|##\s+EXT\.))"),
    re.compile(r"(?is)^\s*let's.*?(?=\n\s*(?:#\s*)?(?:ESCENA\b|INT\.|EXT\.|##\s+INT\.|##\s+EXT\.))"),
)


def clean_model_output(text: str) -> tuple[str, bool, str]:
    """Remove visible reasoning/chatbot preambles while preserving valid scenes."""

    normalized = text.strip()
    if not normalized:
        return normalized, False, ""

    without_think = THINK_BLOCK_PATTERN.sub("", normalized).strip()
    if without_think != normalized:
        normalized = without_think
        start_match = VALID_SCENE_START_PATTERN.search(normalized)
        if start_match and start_match.start() > 0:
            normalized = normalized[start_match.start() :].strip()
        return normalized, True, "removed visible thinking block"

    start_match = VALID_SCENE_START_PATTERN.search(normalized)
    if start_match and start_match.start() > 0:
        return (
            normalized[start_match.start() :].strip(),
            True,
            "trimmed text before valid scene heading",
        )

    for pattern in META_LINE_PATTERNS:
        cleaned = pattern.sub("", normalized).strip()
        if cleaned != normalized:
            return cleaned, True, "removed visible reasoning preamble"

    if CHATBOT_PREFIX_PATTERN.match(normalized):
        lines = normalized.splitlines()
        for index, line in enumerate(lines):
            if VALID_SCENE_START_PATTERN.match(line):
                return "\n".join(lines[index:]).strip(), True, "trimmed chatbot preamble"
        if len(lines) > 1 and not lines[0].strip().startswith("#"):
            return "\n".join(lines[1:]).strip(), True, "removed first chatbot-style line"

    return normalized, False, ""


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
    source_draft_number: int | None = None,
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
        source_draft_number=source_draft_number,
        client=client,
    )


def generate_and_save(
    *,
    series_root: Path,
    source: SceneSource,
    settings: GenerationSettings,
    prompt: str,
    user_feedback: str,
    source_draft_number: int | None = None,
    client: OllamaClient | None = None,
) -> DraftRecord:
    """Call Ollama, build draft metadata, and persist the result."""

    active_client = client or OllamaClient()
    raw_response = active_client.generate(
        model=settings.model,
        prompt=prompt,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )
    response, cleaned_response, cleanup_reason = clean_model_output(raw_response)
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
        cleaned_response=cleaned_response,
        cleanup_reason=cleanup_reason,
        prompt_version=PROMPT_VERSION,
        source_draft_number=source_draft_number,
    )
    save_draft(series_root, source.session_id, record)
    return record
