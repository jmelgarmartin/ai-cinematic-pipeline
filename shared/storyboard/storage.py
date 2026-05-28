"""Storage helpers for storyboard breakdown inputs and outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import StoryboardRecord, StoryboardSource
from .storyboard_generator import storyboard_to_json_payload, storyboard_to_markdown


FINAL_SCREENPLAY_DIR = Path("processing") / "final_screenplay"
STORYBOARD_BREAKDOWN_DIR = Path("processing") / "storyboard_breakdown"
FINAL_SCENE_PATTERN = "escena_*.final.md"


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
    """Return sessions with accepted final screenplay scenes."""

    final_root = root / FINAL_SCREENPLAY_DIR
    if not final_root.is_dir():
        return []
    return sorted(
        path.name for path in final_root.iterdir() if path.is_dir() and any(path.glob(FINAL_SCENE_PATTERN))
    )


def list_scene_ids(root: Path, session_id: str) -> list[str]:
    """Return accepted final screenplay scene IDs."""

    session_dir = root / FINAL_SCREENPLAY_DIR / session_id
    if not session_dir.is_dir():
        return []
    scene_ids: list[str] = []
    for path in sorted(session_dir.glob(FINAL_SCENE_PATTERN)):
        scene_ids.append(path.name.removesuffix(".final.md"))
    return scene_ids


def sha256_text(text: str) -> str:
    """Hash UTF-8 text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_storyboard_source(
    root: Path,
    series_name: str,
    session_id: str,
    scene_id: str,
) -> StoryboardSource:
    """Load the accepted final screenplay for one scene."""

    final_path = root / FINAL_SCREENPLAY_DIR / session_id / f"{scene_id}.final.md"
    if not final_path.exists():
        raise FileNotFoundError(f"Final screenplay not found: {final_path}")
    markdown = final_path.read_text(encoding="utf-8")
    return StoryboardSource(
        series_name=series_name,
        session_id=session_id,
        scene_id=scene_id,
        final_screenplay_path=final_path,
        final_screenplay_markdown=markdown,
        source_hash=sha256_text(markdown),
    )


def storyboard_dir(root: Path, session_id: str) -> Path:
    """Return the storyboard output directory for one session."""

    return root / STORYBOARD_BREAKDOWN_DIR / session_id


def storyboard_paths(root: Path, session_id: str, scene_id: str) -> tuple[Path, Path]:
    """Return JSON and markdown storyboard output paths."""

    directory = storyboard_dir(root, session_id)
    return directory / f"{scene_id}.storyboard.json", directory / f"{scene_id}.storyboard.md"


def save_storyboard(root: Path, session_id: str, record: StoryboardRecord) -> None:
    """Persist storyboard JSON and markdown."""

    directory = storyboard_dir(root, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    json_path, md_path = storyboard_paths(root, session_id, record.scene_id)
    json_path.write_text(
        json.dumps(storyboard_to_json_payload(record), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(storyboard_to_markdown(record), encoding="utf-8")


def read_storyboard_json(root: Path, session_id: str, scene_id: str) -> dict[str, object] | None:
    """Read a persisted storyboard JSON payload."""

    json_path, _md_path = storyboard_paths(root, session_id, scene_id)
    if not json_path.exists():
        return None
    return json.loads(json_path.read_text(encoding="utf-8"))


def read_storyboard_markdown(root: Path, session_id: str, scene_id: str) -> str:
    """Read a persisted storyboard markdown payload."""

    _json_path, md_path = storyboard_paths(root, session_id, scene_id)
    if not md_path.exists():
        return ""
    return md_path.read_text(encoding="utf-8")
