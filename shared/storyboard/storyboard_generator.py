"""Generate structured storyboard breakdowns from final screenplay scenes."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import re

from shared.scene_editor.config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from shared.scene_editor.ollama_client import OllamaClient

from .beat_extractor import extract_candidate_beats
from .models import StoryboardRecord, StoryboardSettings, StoryboardShot, StoryboardSource
from .shot_rules import CAMERA_MOTIONS, PROMPT_VERSION, SHOT_TYPES, STORYBOARD_RULES


JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def default_settings() -> StoryboardSettings:
    """Return default storyboard generation settings."""

    return StoryboardSettings(
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
    )


def build_storyboard_prompt(source: StoryboardSource) -> str:
    """Build the strict structured prompt for storyboard generation."""

    candidate_beats = extract_candidate_beats(source.final_screenplay_markdown)
    beats_text = "\n\n".join(
        f"BEAT {index:03d}\n{beat}" for index, beat in enumerate(candidate_beats, start=1)
    )
    return f"""{STORYBOARD_RULES}

Vocabulario recomendado:
- shot_type: {", ".join(SHOT_TYPES)}
- camera_motion: {", ".join(CAMERA_MOTIONS)}

Tarea:
Genera el storyboard audiovisual estructurado para `{source.scene_id}`.
Divide la escena en shots razonables y continuos. Usa entre 4 y 14 shots salvo
que la escena sea extremadamente corta o larga.

Escena final:
{source.final_screenplay_markdown}

Beats candidatos:
{beats_text or "_Sin beats candidatos._"}
"""


def generate_storyboard(
    *,
    source: StoryboardSource,
    settings: StoryboardSettings,
    client: OllamaClient | None = None,
) -> StoryboardRecord:
    """Generate and parse one storyboard breakdown."""

    prompt = build_storyboard_prompt(source)
    active_client = client or OllamaClient()
    raw_response = active_client.generate(
        model=settings.model,
        prompt=prompt,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )
    shots = parse_storyboard_response(raw_response, expected_scene_id=source.scene_id)
    return StoryboardRecord(
        scene_id=source.scene_id,
        model=settings.model,
        temperature=settings.temperature,
        timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
        source_hash=source.source_hash,
        prompt=prompt,
        prompt_version=PROMPT_VERSION,
        source_screenplay=source.final_screenplay_markdown,
        shots=shots,
    )


def parse_storyboard_response(response: str, *, expected_scene_id: str) -> list[StoryboardShot]:
    """Parse model JSON into storyboard shots."""

    payload = clean_json_response(response)
    data = json.loads(payload)
    if data.get("scene_id") != expected_scene_id:
        data["scene_id"] = expected_scene_id
    raw_shots = data.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("Storyboard response does not contain a non-empty shots list.")

    shots: list[StoryboardShot] = []
    for index, raw_shot in enumerate(raw_shots, start=1):
        if not isinstance(raw_shot, dict):
            raise ValueError(f"Invalid shot at index {index}.")
        shots.append(
            StoryboardShot(
                shot_id=int(raw_shot.get("shot_id") or index),
                shot_type=str(raw_shot.get("shot_type") or "wide"),
                camera_motion=str(raw_shot.get("camera_motion") or "static"),
                location=str(raw_shot.get("location") or ""),
                time_of_day=str(raw_shot.get("time_of_day") or ""),
                description=str(raw_shot.get("description") or ""),
                mood=str(raw_shot.get("mood") or ""),
                lighting=str(raw_shot.get("lighting") or ""),
                focus_subject=str(raw_shot.get("focus_subject") or ""),
                visual_elements=normalize_visual_elements(raw_shot.get("visual_elements")),
                duration_estimate_seconds=normalize_duration(
                    raw_shot.get("duration_estimate_seconds")
                ),
            )
        )
    return shots


def normalize_visual_elements(value: object) -> list[str]:
    """Normalize model visual elements into a clean list of strings."""

    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def normalize_duration(value: object) -> int:
    """Normalize model duration output into a bounded integer."""

    if isinstance(value, int):
        return min(max(value, 2), 10)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return min(max(int(match.group(0)), 2), 10)
    return 4


def clean_json_response(response: str) -> str:
    """Remove common code fences and trim to the outer JSON object."""

    text = JSON_FENCE_PATTERN.sub("", response.strip()).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Storyboard response is not JSON.")
    return text[start : end + 1]


def storyboard_to_json_payload(record: StoryboardRecord) -> dict[str, object]:
    """Return the persisted storyboard JSON payload."""

    return {
        "scene_id": record.scene_id,
        "shots": [asdict(shot) for shot in record.shots],
        "metadata": {
            "model": record.model,
            "temperature": record.temperature,
            "timestamp": record.timestamp,
            "source_hash": record.source_hash,
            "prompt_version": record.prompt_version,
        },
        "prompt": record.prompt,
        "source_screenplay": record.source_screenplay,
    }


def storyboard_to_markdown(record: StoryboardRecord) -> str:
    """Render one storyboard record as readable markdown."""

    heading = record.scene_id.replace("_", " ").upper()
    lines = [
        f"# {heading} STORYBOARD",
        "",
        f"Model: {record.model}",
        f"Prompt version: {record.prompt_version}",
        f"Generated: {record.timestamp}",
        "",
    ]
    for shot in record.shots:
        lines.extend(
            [
                f"## SHOT {shot.shot_id:03d}",
                f"Type: {shot.shot_type}",
                f"Camera motion: {shot.camera_motion}",
                f"Location: {shot.location}",
                f"Time of day: {shot.time_of_day}",
                f"Mood: {shot.mood}",
                f"Lighting: {shot.lighting}",
                f"Focus subject: {shot.focus_subject}",
                f"Duration: {shot.duration_estimate_seconds}s",
                "Visual elements:",
                *[f"- {element}" for element in shot.visual_elements],
                "",
                "Description:",
                shot.description,
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"
