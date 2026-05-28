"""Storage helpers for reviewed and locked visual bibles."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from .models import LockedVisualBible
from .normalizer import locked_visual_bible_to_payload, payload_to_locked_visual_bible
from .storage import visual_bible_dir


LOCKED_VISUAL_BIBLE_FILENAME = "visual_bible.locked.json"
REVIEW_HISTORY_FILENAME = "review_history.json"


def locked_visual_bible_path(root: Path, session_id: str) -> Path:
    """Return locked visual bible path."""

    return visual_bible_dir(root, session_id) / LOCKED_VISUAL_BIBLE_FILENAME


def review_history_path(root: Path, session_id: str) -> Path:
    """Return review history path."""

    return visual_bible_dir(root, session_id) / REVIEW_HISTORY_FILENAME


def save_locked_visual_bible(
    root: Path,
    session_id: str,
    locked: LockedVisualBible,
    *,
    note: str = "",
) -> None:
    """Persist locked visual bible and append review history."""

    directory = visual_bible_dir(root, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    payload = locked_visual_bible_to_payload(locked)
    locked_visual_bible_path(root, session_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_review_history(root, session_id, locked, note=note)


def read_locked_visual_bible(root: Path, session_id: str) -> dict[str, object] | None:
    """Read locked visual bible JSON payload."""

    path = locked_visual_bible_path(root, session_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_locked_visual_bible(root: Path, session_id: str) -> LockedVisualBible | None:
    """Load locked visual bible as typed model."""

    payload = read_locked_visual_bible(root, session_id)
    if payload is None:
        return None
    return payload_to_locked_visual_bible(payload)


def append_review_history(
    root: Path,
    session_id: str,
    locked: LockedVisualBible,
    *,
    note: str = "",
) -> None:
    """Append a compact lock event to review history."""

    path = review_history_path(root, session_id)
    history = read_review_history(root, session_id)
    history.append(
        {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "event": "visual_bible_locked",
            "note": note,
            "character_ids": [character.character_id for character in locked.characters],
            "environment_ids": [
                environment.environment_id for environment in locked.environments
            ],
            "validation_warnings": locked.validation_warnings,
            "source_hashes": locked.source_hashes,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_review_history(root: Path, session_id: str) -> list[dict[str, object]]:
    """Read review history events."""

    path = review_history_path(root, session_id)
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else []


def locked_visual_bible_to_markdown(locked: LockedVisualBible) -> str:
    """Render locked visual bible as readable review markdown."""

    lines = [
        "# LOCKED VISUAL BIBLE",
        "",
        f"Session: {locked.session_id}",
        f"Locked: {locked.locked_at}",
        "",
        "## Characters",
    ]
    for character in locked.characters:
        lines.extend(
            [
                f"### {character.display_name}",
                f"- ID: {character.character_id}",
                "- Appearance:",
                *[f"  - {key}: {value}" for key, value in character.appearance.items()],
                "- Props:",
                *[f"  - {item}" for item in character.props],
                "- Behavioral visuals:",
                *[f"  - {item}" for item in character.behavioral_visuals],
                "",
            ]
        )
    lines.append("## Environments")
    for environment in locked.environments:
        lines.extend(
            [
                f"### {environment.display_name}",
                f"- ID: {environment.environment_id}",
                f"- Aliases: {', '.join(environment.aliases)}",
                f"- Architecture: {environment.architecture}",
                f"- Weather: {environment.weather}",
                f"- Street density: {environment.street_density}",
                f"- Lighting: {environment.lighting}",
                "- Texture:",
                *[f"  - {item}" for item in environment.texture],
                "",
            ]
        )
    if locked.validation_warnings:
        lines.extend(["## Validation Warnings", *[f"- {item}" for item in locked.validation_warnings]])
    return "\n".join(lines).strip() + "\n"
