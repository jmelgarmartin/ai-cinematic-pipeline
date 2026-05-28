"""Review helpers for locking visual bible canon."""

from __future__ import annotations

from datetime import datetime
import json

from .models import LockedVisualBible
from .normalizer import (
    locked_visual_bible_to_payload,
    normalize_visual_bible,
    payload_to_locked_visual_bible,
    validate_locked_visual_bible,
)


def build_locked_visual_bible(visual_bible: dict[str, object]) -> LockedVisualBible:
    """Build a normalized locked visual bible from generated source JSON."""

    return normalize_visual_bible(visual_bible)


def parse_locked_payload(raw_json: str) -> LockedVisualBible:
    """Parse edited JSON and refresh validation warnings."""

    payload = json.loads(raw_json)
    if not isinstance(payload, dict):
        raise ValueError("Locked visual bible must be a JSON object.")
    locked = payload_to_locked_visual_bible(payload)
    return refresh_validation(locked)


def refresh_validation(locked: LockedVisualBible) -> LockedVisualBible:
    """Return a copy with current validation warnings."""

    return LockedVisualBible(
        session_id=locked.session_id,
        locked_at=locked.locked_at
        or datetime.now().astimezone().isoformat(timespec="seconds"),
        source_hashes=locked.source_hashes,
        source_metadata=locked.source_metadata,
        characters=locked.characters,
        environments=locked.environments,
        cinematography=locked.cinematography,
        series_visual_identity=locked.series_visual_identity,
        validation_warnings=validate_locked_visual_bible(locked),
    )


def render_locked_json(locked: LockedVisualBible) -> str:
    """Render locked visual bible as stable compact JSON."""

    return json.dumps(locked_visual_bible_to_payload(locked), ensure_ascii=False, indent=2)
