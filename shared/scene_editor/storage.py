"""File storage helpers for scene editor inputs, drafts, and finals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import DraftRecord, SceneSource


SCREENPLAY_DIR = Path("processing") / "screenplay"
EDITORIAL_NOTES_DIR = Path("editorial_notes")
ANNOTATED_SCREENPLAY_DIR = Path("processing") / "annotated_screenplay"
FINAL_SCREENPLAY_DIR = Path("processing") / "final_screenplay"
SCREENPLAY_SCENE_PATTERN = "escena_*.md"
CONVERSATION_HISTORY_FILE = "conversation_history.json"


def project_root() -> Path:
    """Resolve the project root from this module location."""

    return Path(__file__).resolve().parents[2]


def series_root(series_name: str) -> Path:
    """Resolve a series root directory."""

    root = project_root() / series_name
    if not root.is_dir():
        raise FileNotFoundError(f"Series not found: {root}")
    return root


def list_series() -> list[str]:
    """Return plausible local series directories."""

    excluded = {".git", ".venv", "__pycache__", "docs", "shared"}
    return sorted(
        path.name
        for path in project_root().iterdir()
        if path.is_dir() and path.name not in excluded and not path.name.startswith(".")
    )


def list_sessions(root: Path) -> list[str]:
    """Return sessions that have screenplay scenes."""

    screenplay_root = root / SCREENPLAY_DIR
    if not screenplay_root.is_dir():
        return []
    return sorted(
        path.name
        for path in screenplay_root.iterdir()
        if path.is_dir() and any(path.glob(SCREENPLAY_SCENE_PATTERN))
    )


def list_scene_ids(root: Path, session_id: str) -> list[str]:
    """Return screenplay scene IDs in deterministic order."""

    session_dir = root / SCREENPLAY_DIR / session_id
    if not session_dir.is_dir():
        return []
    return [path.stem for path in sorted(session_dir.glob(SCREENPLAY_SCENE_PATTERN))]


def sha256_text(text: str) -> str:
    """Hash UTF-8 text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text_if_exists(path: Path) -> str:
    """Read text or return an empty string when the file is missing."""

    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_scene_source(root: Path, series_name: str, session_id: str, scene_id: str) -> SceneSource:
    """Load all source materials for one scene."""

    screenplay_path = root / SCREENPLAY_DIR / session_id / f"{scene_id}.md"
    notes_path = root / EDITORIAL_NOTES_DIR / session_id / f"{scene_id}.notes.md"
    annotated_path = root / ANNOTATED_SCREENPLAY_DIR / session_id / f"{scene_id}.annotated.json"
    if not screenplay_path.exists():
        raise FileNotFoundError(f"Screenplay scene not found: {screenplay_path}")

    screenplay_markdown = screenplay_path.read_text(encoding="utf-8")
    editorial_notes_markdown = read_text_if_exists(notes_path)
    annotated_json = read_text_if_exists(annotated_path)
    return SceneSource(
        series_name=series_name,
        session_id=session_id,
        scene_id=scene_id,
        screenplay_path=screenplay_path,
        notes_path=notes_path,
        annotated_path=annotated_path if annotated_path.exists() else None,
        screenplay_markdown=screenplay_markdown,
        editorial_notes_markdown=editorial_notes_markdown,
        annotated_json=annotated_json,
        source_hash=sha256_text(screenplay_markdown),
        editorial_hash=sha256_text(editorial_notes_markdown),
    )


def draft_dir(root: Path, session_id: str, scene_id: str) -> Path:
    """Return the draft directory for one scene."""

    return root / FINAL_SCREENPLAY_DIR / session_id / "drafts" / scene_id


def final_dir(root: Path, session_id: str) -> Path:
    """Return the final screenplay directory for one session."""

    return root / FINAL_SCREENPLAY_DIR / session_id


def list_draft_numbers(root: Path, session_id: str, scene_id: str) -> list[int]:
    """Return available draft numbers for one scene."""

    directory = draft_dir(root, session_id, scene_id)
    if not directory.is_dir():
        return []
    numbers: list[int] = []
    for path in directory.glob("draft_*.json"):
        try:
            numbers.append(int(path.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return sorted(numbers)


def next_draft_number(root: Path, session_id: str, scene_id: str) -> int:
    """Return the next draft number for one scene."""

    numbers = list_draft_numbers(root, session_id, scene_id)
    return numbers[-1] + 1 if numbers else 1


def save_draft(root: Path, session_id: str, record: DraftRecord) -> None:
    """Persist draft markdown, metadata JSON, and conversation history."""

    directory = draft_dir(root, session_id, record.scene_id)
    directory.mkdir(parents=True, exist_ok=True)
    draft_name = f"draft_{record.draft_number:03d}"
    (directory / f"{draft_name}.md").write_text(record.response + "\n", encoding="utf-8")
    (directory / f"{draft_name}.json").write_text(
        json.dumps(asdict(record), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_history(directory, record)


def append_history(directory: Path, record: DraftRecord) -> None:
    """Append a draft to conversation_history.json."""

    history_path = directory / CONVERSATION_HISTORY_FILE
    if history_path.exists():
        data = json.loads(history_path.read_text(encoding="utf-8"))
        history = data.get("drafts", [])
        if not isinstance(history, list):
            history = []
    else:
        history = []
    history.append(asdict(record))
    history_path.write_text(
        json.dumps({"drafts": history}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_draft(root: Path, session_id: str, scene_id: str, draft_number: int) -> DraftRecord:
    """Load one persisted draft metadata record."""

    path = draft_dir(root, session_id, scene_id) / f"draft_{draft_number:03d}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return DraftRecord(
        scene_id=str(data["scene_id"]),
        draft_number=int(data["draft_number"]),
        model=str(data["model"]),
        temperature=float(data["temperature"]),
        timestamp=str(data["timestamp"]),
        source_hash=str(data["source_hash"]),
        editorial_hash=str(data["editorial_hash"]),
        user_feedback=str(data.get("user_feedback", "")),
        prompt=str(data["prompt"]),
        response=str(data["response"]),
        cleaned_response=bool(data.get("cleaned_response", False)),
        cleanup_reason=str(data.get("cleanup_reason", "")),
        prompt_version=str(data.get("prompt_version", "scene_editor_v1")),
    )


def latest_draft(root: Path, session_id: str, scene_id: str) -> DraftRecord | None:
    """Return the latest draft record, if any."""

    numbers = list_draft_numbers(root, session_id, scene_id)
    if not numbers:
        return None
    return load_draft(root, session_id, scene_id, numbers[-1])


def save_final(root: Path, session_id: str, record: DraftRecord) -> None:
    """Mark a draft as the accepted final screenplay for a scene."""

    directory = final_dir(root, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    base_name = f"{record.scene_id}.final"
    (directory / f"{base_name}.md").write_text(record.response + "\n", encoding="utf-8")
    payload: dict[str, Any] = asdict(record)
    payload["accepted_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    (directory / f"{base_name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def final_paths(root: Path, session_id: str, scene_id: str) -> tuple[Path, Path]:
    """Return final markdown and JSON paths for one scene."""

    directory = final_dir(root, session_id)
    return directory / f"{scene_id}.final.md", directory / f"{scene_id}.final.json"
