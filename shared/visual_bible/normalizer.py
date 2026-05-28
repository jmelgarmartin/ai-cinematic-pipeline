"""Normalize generated visual bibles into a compact canonical lock format."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import re
from typing import Any

from .models import (
    CinematographyRules,
    LockedCharacterProfile,
    LockedEnvironmentProfile,
    LockedVisualBible,
    SeriesVisualIdentity,
)
from .visual_bible_generator import parse_cinematography, parse_series_identity


CHARACTER_OVERRIDES: dict[str, dict[str, object]] = {
    "olivia": {
        "appearance": {
            "hair": "black",
            "clothing": "black clothing",
        },
        "props": ["sunglasses hanging from shirt collar"],
        "behavioral_visuals": ["chewing gum habit"],
    },
    "river": {
        "appearance": {
            "hair": "blond low ponytail",
            "face": "marked under-eyes",
        },
        "props": ["coffee cup"],
        "behavioral_visuals": ["coffee cup habit"],
    },
    "clara": {
        "appearance": {
            "hair": "red hair",
            "hairstyle": "messy bun",
        },
        "props": ["portfolio", "pens", "two coffees"],
    },
}


PROP_KEYS = {"prop", "props", "accessory", "accessories"}
HAIR_COLORS = {
    "black",
    "blond",
    "blonde",
    "red",
    "brown",
    "grey",
    "gray",
    "white",
}


def normalize_visual_bible(
    visual_bible: dict[str, object],
    *,
    locked_at: str | None = None,
) -> LockedVisualBible:
    """Build the default locked visual bible from a generated visual bible."""

    metadata = normalized_dict(visual_bible.get("metadata"))
    session_id = str(metadata.get("session_id") or "")
    source_hashes = {
        "screenplay_hash": str(metadata.get("screenplay_hash") or ""),
        "storyboard_hash": str(metadata.get("storyboard_hash") or ""),
    }
    source_metadata = {
        "model": metadata.get("model", ""),
        "temperature": metadata.get("temperature", ""),
        "timestamp": metadata.get("timestamp", ""),
        "prompt_version": metadata.get("prompt_version", ""),
    }
    characters = normalize_characters(visual_bible.get("characters"))
    environments = normalize_environments(visual_bible.get("environments"))
    cinematography = parse_cinematography(visual_bible.get("cinematography"))
    identity = parse_series_identity(visual_bible.get("series_visual_identity"))
    locked = LockedVisualBible(
        session_id=session_id,
        locked_at=locked_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        source_hashes=source_hashes,
        source_metadata=source_metadata,
        characters=characters,
        environments=environments,
        cinematography=cinematography,
        series_visual_identity=identity,
        validation_warnings=[],
    )
    warnings = validate_locked_visual_bible(locked)
    return LockedVisualBible(
        session_id=locked.session_id,
        locked_at=locked.locked_at,
        source_hashes=locked.source_hashes,
        source_metadata=locked.source_metadata,
        characters=locked.characters,
        environments=locked.environments,
        cinematography=locked.cinematography,
        series_visual_identity=locked.series_visual_identity,
        validation_warnings=warnings,
    )


def normalize_characters(value: object) -> list[LockedCharacterProfile]:
    """Merge generated character entries into stable character profiles."""

    grouped: dict[str, list[dict[str, object]]] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            character_id = canonical_character_id(str(item.get("character_id") or ""))
            if not character_id:
                continue
            grouped.setdefault(character_id, []).append(item)

    profiles: list[LockedCharacterProfile] = []
    for character_id in sorted(grouped):
        items = grouped[character_id]
        appearance: dict[str, str] = {}
        props: list[str] = []
        behavioral_visuals: list[str] = []
        camera_treatment: dict[str, object] = {}
        source_ids: list[str] = []

        for item in items:
            source_ids.append(str(item.get("character_id") or character_id))
            item_appearance = normalized_dict(item.get("appearance"))
            for key, raw_value in item_appearance.items():
                normalized_key = normalize_key(key)
                if normalized_key in PROP_KEYS:
                    props.extend(split_items(raw_value))
                elif str(raw_value).strip():
                    appearance.setdefault(normalized_key, str(raw_value).strip())
            props.extend(split_items(item.get("props")))
            behavioral_visuals.extend(split_items(item.get("behavioral_visuals")))
            camera_treatment.update(normalized_dict(item.get("camera_treatment")))

        overrides = CHARACTER_OVERRIDES.get(character_id, {})
        appearance.update(normalized_string_dict(overrides.get("appearance")))
        props.extend(split_items(overrides.get("props")))
        behavioral_visuals.extend(split_items(overrides.get("behavioral_visuals")))

        profiles.append(
            LockedCharacterProfile(
                character_id=character_id,
                display_name=character_id.title(),
                appearance=appearance,
                props=dedupe_preserve_order(props),
                behavioral_visuals=dedupe_preserve_order(behavioral_visuals),
                camera_treatment=camera_treatment,
                source_character_ids=dedupe_preserve_order(source_ids),
            )
        )
    return profiles


def normalize_environments(value: object) -> list[LockedEnvironmentProfile]:
    """Merge generated locations into stable environment profiles."""

    grouped: dict[str, list[dict[str, object]]] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            location = str(item.get("location") or "")
            environment_id = canonical_environment_id(location)
            if not environment_id:
                continue
            grouped.setdefault(environment_id, []).append(item)

    profiles: list[LockedEnvironmentProfile] = []
    for environment_id in sorted(grouped):
        items = grouped[environment_id]
        aliases: list[str] = []
        texture: list[str] = []
        architecture = ""
        weather = ""
        street_density = ""
        lighting = ""
        for item in items:
            aliases.append(str(item.get("location") or ""))
            architecture = architecture or str(item.get("architecture") or "").strip()
            weather = weather or str(item.get("weather") or "").strip()
            street_density = street_density or str(item.get("street_density") or "").strip()
            lighting = lighting or str(item.get("lighting") or "").strip()
            texture.extend(split_items(item.get("texture")))

        profiles.append(
            LockedEnvironmentProfile(
                environment_id=environment_id,
                display_name=environment_display_name(environment_id),
                aliases=dedupe_preserve_order(aliases),
                architecture=architecture,
                weather=weather,
                street_density=street_density,
                texture=dedupe_preserve_order(texture),
                lighting=lighting,
            )
        )
    return profiles


def locked_visual_bible_to_payload(locked: LockedVisualBible) -> dict[str, object]:
    """Convert a locked visual bible into compact JSON payload."""

    return {
        "metadata": {
            "session_id": locked.session_id,
            "locked_at": locked.locked_at,
            "source_hashes": locked.source_hashes,
            "source_metadata": locked.source_metadata,
            "schema": "visual_bible.locked.v1",
        },
        "characters": [asdict(character) for character in locked.characters],
        "environments": [asdict(environment) for environment in locked.environments],
        "cinematography": asdict(locked.cinematography),
        "series_visual_identity": asdict(locked.series_visual_identity),
        "validation_warnings": locked.validation_warnings,
    }


def payload_to_locked_visual_bible(payload: dict[str, object]) -> LockedVisualBible:
    """Parse compact locked JSON payload."""

    metadata = normalized_dict(payload.get("metadata"))
    return LockedVisualBible(
        session_id=str(metadata.get("session_id") or ""),
        locked_at=str(metadata.get("locked_at") or ""),
        source_hashes=normalized_string_dict(metadata.get("source_hashes")),
        source_metadata=normalized_dict(metadata.get("source_metadata")),
        characters=[
            LockedCharacterProfile(
                character_id=str(item.get("character_id") or ""),
                display_name=str(item.get("display_name") or ""),
                appearance=normalized_string_dict(item.get("appearance")),
                props=split_items(item.get("props")),
                behavioral_visuals=split_items(item.get("behavioral_visuals")),
                camera_treatment=normalized_dict(item.get("camera_treatment")),
                source_character_ids=split_items(item.get("source_character_ids")),
            )
            for item in payload.get("characters", [])
            if isinstance(item, dict)
        ],
        environments=[
            LockedEnvironmentProfile(
                environment_id=str(item.get("environment_id") or ""),
                display_name=str(item.get("display_name") or ""),
                aliases=split_items(item.get("aliases")),
                architecture=str(item.get("architecture") or ""),
                weather=str(item.get("weather") or ""),
                street_density=str(item.get("street_density") or ""),
                texture=split_items(item.get("texture")),
                lighting=str(item.get("lighting") or ""),
            )
            for item in payload.get("environments", [])
            if isinstance(item, dict)
        ],
        cinematography=parse_cinematography(payload.get("cinematography")),
        series_visual_identity=parse_series_identity(payload.get("series_visual_identity")),
        validation_warnings=split_items(payload.get("validation_warnings")),
    )


def validate_locked_visual_bible(locked: LockedVisualBible) -> list[str]:
    """Return validation warnings for locked canon."""

    warnings: list[str] = []
    character_ids = [character.character_id for character in locked.characters]
    if any(not character_id for character_id in character_ids):
        warnings.append("missing character id")
    for character_id in sorted(find_duplicates(character_ids)):
        warnings.append(f"duplicated character id: {character_id}")
    for character in locked.characters:
        if not character.appearance:
            warnings.append(f"empty appearance: {character.character_id}")
        hair_values = [
            value
            for key, value in character.appearance.items()
            if "hair" in key and value
        ]
        if has_contradictory_hair_values(hair_values):
            warnings.append(f"contradictory hair attributes: {character.character_id}")

    environment_ids = [environment.environment_id for environment in locked.environments]
    for environment_id in sorted(find_duplicates(environment_ids)):
        warnings.append(f"duplicated location: {environment_id}")
    return warnings


def canonical_character_id(value: str) -> str:
    """Normalize a character name into a stable id."""

    return normalize_key(value).replace("-", "_")


def canonical_environment_id(location: str) -> str:
    """Normalize a generated location into a stable environment id."""

    lowered = location.lower()
    if "miletown" in lowered:
        return "miletown_exterior"
    if any(token in lowered for token in ["cafeter", "cafe", "local", "peque"]):
        if "exterior" in lowered or "zona sur" in lowered or "south" in lowered:
            return "south_side_cafe_exterior"
        return "south_side_cafe_interior"
    return normalize_key(location).replace("-", "_")


def environment_display_name(environment_id: str) -> str:
    """Return a readable name for a canonical environment id."""

    names = {
        "miletown_exterior": "Miletown Exterior",
        "south_side_cafe_exterior": "South Side Cafe Exterior",
        "south_side_cafe_interior": "South Side Cafe Interior",
    }
    return names.get(environment_id, environment_id.replace("_", " ").title())


def normalize_key(value: object) -> str:
    """Normalize a dict key or free-form label."""

    text = str(value or "").strip().lower()
    text = re.sub(r"[^\w]+", "_", text, flags=re.UNICODE)
    return text.strip("_")


def normalized_dict(value: object) -> dict[str, Any]:
    """Return dict-like values only."""

    return dict(value) if isinstance(value, dict) else {}


def normalized_string_dict(value: object) -> dict[str, str]:
    """Return a string-only dictionary."""

    return {
        str(key): str(item)
        for key, item in normalized_dict(value).items()
        if str(item).strip()
    }


def split_items(value: object) -> list[str]:
    """Normalize a string or list into clean string items."""

    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(split_items(item))
        return items
    if isinstance(value, str):
        if not value.strip():
            return []
        parts = re.split(r"\s*,\s*|\s*;\s*", value)
        return [part.strip() for part in parts if part.strip()]
    if value:
        return [str(value)]
    return []


def dedupe_preserve_order(items: list[str]) -> list[str]:
    """Deduplicate while preserving first useful casing."""

    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        cleaned = str(item).strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            deduped.append(cleaned)
    return deduped


def find_duplicates(items: list[str]) -> set[str]:
    """Return duplicated non-empty items."""

    seen: set[str] = set()
    duplicated: set[str] = set()
    for item in items:
        if not item:
            continue
        if item in seen:
            duplicated.add(item)
        seen.add(item)
    return duplicated


def has_contradictory_hair_values(values: list[str]) -> bool:
    """Detect obvious contradictory hair color assignments."""

    colors: set[str] = set()
    for value in values:
        words = set(re.findall(r"[a-z]+", value.lower()))
        colors.update(words & HAIR_COLORS)
    return len(colors) > 1
