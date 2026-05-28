"""Generate a reusable visual bible from screenplay and storyboard sources."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
import re

from shared.scene_editor.config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from shared.scene_editor.ollama_client import OllamaClient

from .character_extractor import extract_character_hints
from .cinematography_rules import PROMPT_VERSION, VISUAL_BIBLE_RULES
from .environment_extractor import extract_environment_hints
from .models import (
    CharacterVisualProfile,
    CinematographyRules,
    EnvironmentRule,
    SeriesVisualIdentity,
    VisualBibleRecord,
    VisualBibleSettings,
    VisualBibleSource,
)


JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def default_settings() -> VisualBibleSettings:
    """Return default visual bible generation settings."""

    return VisualBibleSettings(
        model=DEFAULT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
    )


def build_visual_bible_prompt(source: VisualBibleSource) -> str:
    """Build a strict prompt for visual bible generation."""

    combined = f"{source.final_screenplay_markdown}\n\n{source.storyboard_json_text}"
    characters = ", ".join(extract_character_hints(combined)) or "_No deterministic hints_"
    environments = ", ".join(extract_environment_hints(combined)) or "_No deterministic hints_"
    return f"""{VISUAL_BIBLE_RULES}

Referencias de identidad visual permitidas:
- True Detective
- Dark
- Chernobyl
- Archive 81

Personajes detectados:
{characters}

Localizaciones detectadas:
{environments}

Screenplay final:
{source.final_screenplay_markdown}

Storyboard breakdown:
{source.storyboard_json_text}
"""


def generate_visual_bible(
    *,
    source: VisualBibleSource,
    settings: VisualBibleSettings,
    client: OllamaClient | None = None,
) -> VisualBibleRecord:
    """Generate and parse one visual bible."""

    prompt = build_visual_bible_prompt(source)
    active_client = client or OllamaClient()
    raw_response = active_client.generate(
        model=settings.model,
        prompt=prompt,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )
    parsed = parse_visual_bible_response(raw_response)
    characters = parsed["characters"]
    fallback_character_profiles = fallback_characters(source)
    if not characters or uses_generic_character_ids(characters):
        characters = fallback_character_profiles
    environments = enrich_environments(parsed["environments"], source)
    return VisualBibleRecord(
        session_id=source.session_id,
        model=settings.model,
        temperature=settings.temperature,
        timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
        screenplay_hash=source.screenplay_hash,
        storyboard_hash=source.storyboard_hash,
        prompt=prompt,
        prompt_version=PROMPT_VERSION,
        source_screenplay=source.final_screenplay_markdown,
        source_storyboard=source.storyboard_json_text,
        characters=characters,
        environments=environments,
        cinematography=parsed["cinematography"],
        series_visual_identity=parsed["series_visual_identity"],
    )


def parse_visual_bible_response(response: str) -> dict[str, object]:
    """Parse model JSON into typed visual bible components."""

    payload = clean_json_response(response)
    data = json.loads(payload)
    parsed = {
        "characters": parse_characters(data.get("characters")),
        "environments": parse_environments(data.get("environments")),
        "cinematography": parse_cinematography(data.get("cinematography")),
        "series_visual_identity": parse_series_identity(
            data.get("series_visual_identity")
        ),
    }
    return parsed


def clean_json_response(response: str) -> str:
    """Remove common code fences and trim to the outer JSON object."""

    text = JSON_FENCE_PATTERN.sub("", response.strip()).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Visual bible response is not JSON.")
    return text[start : end + 1]


def parse_characters(value: object) -> list[CharacterVisualProfile]:
    """Parse character profile list."""

    if not isinstance(value, list):
        return []
    characters: list[CharacterVisualProfile] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        character_id = str(item.get("character_id") or "").strip()
        if not character_id:
            continue
        characters.append(
            CharacterVisualProfile(
                character_id=character_id,
                appearance=dict(item.get("appearance") or {}),
                behavioral_visuals=normalize_string_list(item.get("behavioral_visuals")),
                camera_treatment=dict(item.get("camera_treatment") or {}),
            )
        )
    return characters


def parse_environments(value: object) -> list[EnvironmentRule]:
    """Parse environment rules list."""

    if not isinstance(value, list):
        return []
    environments: list[EnvironmentRule] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        location = str(item.get("location") or "").strip()
        if not location:
            continue
        environments.append(
            EnvironmentRule(
                location=location,
                architecture=str(item.get("architecture") or ""),
                weather=str(item.get("weather") or ""),
                street_density=str(item.get("street_density") or ""),
                texture=normalize_string_list(item.get("texture")),
                lighting=str(item.get("lighting") or ""),
            )
        )
    return environments


def parse_cinematography(value: object) -> CinematographyRules:
    """Parse cinematography rule object."""

    if not isinstance(value, dict):
        value = {}
    return CinematographyRules(
        camera_language=normalize_dict(value.get("camera_language")),
        lighting=normalize_dict(value.get("lighting")),
        color_grading=normalize_dict(value.get("color_grading")),
        composition=normalize_dict(value.get("composition")),
        lenses=normalize_dict(value.get("lenses")),
        texture=normalize_dict(value.get("texture")),
    )


def parse_series_identity(value: object) -> SeriesVisualIdentity:
    """Parse series visual identity object."""

    if not isinstance(value, dict):
        value = {}
    return SeriesVisualIdentity(
        references=normalize_string_list(value.get("references")),
        visual_keywords=normalize_string_list(value.get("visual_keywords")),
        visual_rules=normalize_string_list(value.get("visual_rules")),
    )


def fallback_characters(source: VisualBibleSource) -> list[CharacterVisualProfile]:
    """Build minimal profiles from explicit source text when the model omits them."""

    text = source.final_screenplay_markdown.lower()
    characters: list[CharacterVisualProfile] = []
    if "olivia" in text:
        characters.append(
            CharacterVisualProfile(
                character_id="olivia",
                appearance={
                    "hair": "black",
                    "clothing": "black clothing",
                    "accessories": "sunglasses hanging from shirt collar",
                },
                behavioral_visuals=["chewing gum", "repeated gum bubble"],
                camera_treatment={
                    "preferred_shots": ["close", "static medium"],
                    "visual_feeling": "contained and still",
                },
            )
        )
    if "river" in text:
        characters.append(
            CharacterVisualProfile(
                character_id="river",
                appearance={
                    "hair": "blond low ponytail",
                    "face": "marked under-eyes",
                    "prop": "coffee cup held in both hands",
                },
                behavioral_visuals=["watching Olivia's gum", "holding coffee cup"],
                camera_treatment={
                    "preferred_shots": ["medium", "close reaction"],
                    "visual_feeling": "tight and watchful",
                },
            )
        )
    if "clara" in text:
        characters.append(
            CharacterVisualProfile(
                character_id="clara",
                appearance={
                    "hair": "messy bun",
                    "props": "portfolio, pens, two coffees",
                },
                behavioral_visuals=["taking notes", "looking beyond the table"],
                camera_treatment={
                    "preferred_shots": ["medium", "insert hands"],
                    "visual_feeling": "methodical and observant",
                },
            )
        )
    return characters


def uses_generic_character_ids(characters: list[CharacterVisualProfile]) -> bool:
    """Return true when model output uses placeholder character IDs."""

    if not characters:
        return False
    return all(
        re.fullmatch(r"c(?:haracter)?[_ -]?\d+", character.character_id.lower())
        for character in characters
    )


def fallback_environments(source: VisualBibleSource) -> list[EnvironmentRule]:
    """Build minimal environment rules from explicit source text."""

    text = source.final_screenplay_markdown.lower()
    environments: list[EnvironmentRule] = []
    if "miletown" in text:
        environments.append(
            EnvironmentRule(
                location="Miletown",
                architecture="industrial town with empty high-rises and closed storefronts",
                weather="humid overcast",
                street_density="sparse",
                texture=["wet asphalt", "faded signage", "empty streets"],
                lighting="diffuse grey exterior light",
            )
        )
    if "cafeter" in text:
        environments.append(
            EnvironmentRule(
                location="Cafeteria",
                architecture="small south-side local with glass front",
                weather="interior shelter from humid street",
                street_density="single occupied table",
                texture=[
                    "black-and-white photos",
                    "fryer oil",
                    "coffee steam",
                    "blinking OPEN sign",
                ],
                lighting="warm practical interior light with intermittent OPEN sign flicker",
            )
        )
    return environments


def enrich_environments(
    environments: list[EnvironmentRule],
    source: VisualBibleSource,
) -> list[EnvironmentRule]:
    """Fill empty model environment entries with deterministic source details."""

    fallback = fallback_environments(source)
    if not environments:
        return fallback

    enriched: list[EnvironmentRule] = []
    for environment in environments:
        replacement = matching_environment(environment.location, fallback)
        if replacement and environment_is_sparse(environment):
            enriched.append(
                EnvironmentRule(
                    location=environment.location or replacement.location,
                    architecture=environment.architecture or replacement.architecture,
                    weather=environment.weather or replacement.weather,
                    street_density=environment.street_density or replacement.street_density,
                    texture=environment.texture or replacement.texture,
                    lighting=environment.lighting or replacement.lighting,
                )
            )
        else:
            enriched.append(environment)
    return enriched


def environment_is_sparse(environment: EnvironmentRule) -> bool:
    """Return true when an environment has a name but little reusable detail."""

    return not any(
        [
            environment.architecture,
            environment.weather,
            environment.street_density,
            environment.texture,
            environment.lighting,
        ]
    )


def matching_environment(
    location: str,
    fallback_environments_list: list[EnvironmentRule],
) -> EnvironmentRule | None:
    """Find a broad fallback environment for a model-provided location."""

    normalized = location.lower()
    for fallback in fallback_environments_list:
        fallback_name = fallback.location.lower()
        if fallback_name in normalized or normalized in fallback_name:
            return fallback
        if "miletown" in normalized and "miletown" in fallback_name:
            return fallback
        if "cafeter" in normalized and "cafeter" in fallback_name:
            return fallback
        if "local" in normalized and "cafeter" in fallback_name:
            return fallback
    return None


def normalize_string_list(value: object) -> list[str]:
    """Normalize strings or string lists into a list of clean strings."""

    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def normalize_dict(value: object) -> dict[str, object]:
    """Normalize model dict-like values into a dictionary."""

    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"rules": [str(item) for item in value if str(item).strip()]}
    if isinstance(value, str) and value.strip():
        return {"rules": normalize_string_list(value)}
    return {}


def visual_bible_to_json_payload(record: VisualBibleRecord) -> dict[str, object]:
    """Return persisted visual bible JSON payload."""

    return {
        "characters": [asdict(character) for character in record.characters],
        "environments": [asdict(environment) for environment in record.environments],
        "cinematography": asdict(record.cinematography),
        "series_visual_identity": asdict(record.series_visual_identity),
        "metadata": {
            "session_id": record.session_id,
            "model": record.model,
            "temperature": record.temperature,
            "timestamp": record.timestamp,
            "screenplay_hash": record.screenplay_hash,
            "storyboard_hash": record.storyboard_hash,
            "prompt_version": record.prompt_version,
        },
        "prompt": record.prompt,
        "source_screenplay": record.source_screenplay,
        "source_storyboard": record.source_storyboard,
    }


def visual_bible_to_markdown(record: VisualBibleRecord) -> str:
    """Render visual bible as readable markdown."""

    lines = [
        "# VISUAL BIBLE",
        "",
        f"Session: {record.session_id}",
        f"Model: {record.model}",
        f"Prompt version: {record.prompt_version}",
        f"Generated: {record.timestamp}",
        "",
        "## Character Visual Profiles",
    ]
    for character in record.characters:
        lines.extend(
            [
                f"### {character.character_id}",
                "Appearance:",
                *[f"- {key}: {value}" for key, value in character.appearance.items()],
                "Behavioral visuals:",
                *[f"- {item}" for item in character.behavioral_visuals],
                "Camera treatment:",
                *[
                    f"- {key}: {format_markdown_value(value)}"
                    for key, value in character.camera_treatment.items()
                ],
                "",
            ]
        )

    lines.append("## Environment Rules")
    for environment in record.environments:
        lines.extend(
            [
                f"### {environment.location}",
                f"- Architecture: {environment.architecture}",
                f"- Weather: {environment.weather}",
                f"- Street density: {environment.street_density}",
                f"- Lighting: {environment.lighting}",
                "- Texture:",
                *[f"  - {item}" for item in environment.texture],
                "",
            ]
        )

    lines.extend(
        [
            "## Cinematography Rules",
            "### Camera Language",
            *[
                f"- {key}: {format_markdown_value(value)}"
                for key, value in record.cinematography.camera_language.items()
            ],
            "### Lighting",
            *[
                f"- {key}: {format_markdown_value(value)}"
                for key, value in record.cinematography.lighting.items()
            ],
            "### Color Grading",
            *[
                f"- {key}: {format_markdown_value(value)}"
                for key, value in record.cinematography.color_grading.items()
            ],
            "### Composition",
            *[
                f"- {key}: {format_markdown_value(value)}"
                for key, value in record.cinematography.composition.items()
            ],
            "### Lenses",
            *[
                f"- {key}: {format_markdown_value(value)}"
                for key, value in record.cinematography.lenses.items()
            ],
            "### Texture",
            *[
                f"- {key}: {format_markdown_value(value)}"
                for key, value in record.cinematography.texture.items()
            ],
            "",
            "## Series Visual Identity",
            "References:",
            *[f"- {item}" for item in record.series_visual_identity.references],
            "Visual keywords:",
            *[f"- {item}" for item in record.series_visual_identity.visual_keywords],
            "Visual rules:",
            *[f"- {item}" for item in record.series_visual_identity.visual_rules],
        ]
    )
    return "\n".join(lines).strip() + "\n"


def format_markdown_value(value: object) -> str:
    """Render simple values consistently for markdown."""

    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return "; ".join(f"{key}: {item}" for key, item in value.items())
    return str(value)
