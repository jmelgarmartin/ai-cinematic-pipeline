"""Storage helpers for visual bible inputs and outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import VisualBibleRecord, VisualBibleSource
from .visual_bible_generator import visual_bible_to_json_payload, visual_bible_to_markdown


FINAL_SCREENPLAY_DIR = Path("processing") / "final_screenplay"
STORYBOARD_BREAKDOWN_DIR = Path("processing") / "storyboard_breakdown"
VISUAL_BIBLE_DIR = Path("processing") / "visual_bible"
FINAL_SCENE_PATTERN = "escena_*.final.md"
STORYBOARD_SCENE_PATTERN = "escena_*.storyboard.json"


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
    """Return sessions with both final screenplay and storyboard breakdown."""

    final_root = root / FINAL_SCREENPLAY_DIR
    storyboard_root = root / STORYBOARD_BREAKDOWN_DIR
    if not final_root.is_dir() or not storyboard_root.is_dir():
        return []
    sessions = {
        path.name
        for path in final_root.iterdir()
        if path.is_dir() and any(path.glob(FINAL_SCENE_PATTERN))
    }
    storyboard_sessions = {
        path.name
        for path in storyboard_root.iterdir()
        if path.is_dir() and any(path.glob(STORYBOARD_SCENE_PATTERN))
    }
    return sorted(sessions & storyboard_sessions)


def sha256_text(text: str) -> str:
    """Hash UTF-8 text."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_visual_bible_source(
    root: Path,
    series_name: str,
    session_id: str,
) -> VisualBibleSource:
    """Load all final screenplay and storyboard sources for one session."""

    final_dir = root / FINAL_SCREENPLAY_DIR / session_id
    storyboard_dir = root / STORYBOARD_BREAKDOWN_DIR / session_id
    final_paths = sorted(final_dir.glob(FINAL_SCENE_PATTERN))
    storyboard_paths = sorted(storyboard_dir.glob(STORYBOARD_SCENE_PATTERN))
    if not final_paths:
        raise FileNotFoundError(f"No final screenplay files found in: {final_dir}")
    if not storyboard_paths:
        raise FileNotFoundError(f"No storyboard files found in: {storyboard_dir}")

    screenplay_text = "\n\n".join(path.read_text(encoding="utf-8") for path in final_paths)
    storyboard_text = "\n\n".join(path.read_text(encoding="utf-8") for path in storyboard_paths)
    return VisualBibleSource(
        series_name=series_name,
        session_id=session_id,
        final_screenplay_paths=final_paths,
        storyboard_paths=storyboard_paths,
        final_screenplay_markdown=screenplay_text,
        storyboard_json_text=storyboard_text,
        screenplay_hash=sha256_text(screenplay_text),
        storyboard_hash=sha256_text(storyboard_text),
    )


def visual_bible_dir(root: Path, session_id: str) -> Path:
    """Return visual bible output directory."""

    return root / VISUAL_BIBLE_DIR / session_id


def visual_bible_paths(root: Path, session_id: str) -> tuple[Path, Path]:
    """Return JSON and markdown visual bible paths."""

    directory = visual_bible_dir(root, session_id)
    return directory / "visual_bible.json", directory / "visual_bible.md"


def save_visual_bible(root: Path, session_id: str, record: VisualBibleRecord) -> None:
    """Persist visual bible JSON and markdown."""

    directory = visual_bible_dir(root, session_id)
    directory.mkdir(parents=True, exist_ok=True)
    json_path, md_path = visual_bible_paths(root, session_id)
    json_path.write_text(
        json.dumps(visual_bible_to_json_payload(record), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    md_path.write_text(visual_bible_to_markdown(record), encoding="utf-8")


def read_visual_bible_json(root: Path, session_id: str) -> dict[str, object] | None:
    """Read persisted visual bible JSON."""

    json_path, _md_path = visual_bible_paths(root, session_id)
    if not json_path.exists():
        return None
    return json.loads(json_path.read_text(encoding="utf-8"))


def read_visual_bible_markdown(root: Path, session_id: str) -> str:
    """Read persisted visual bible markdown."""

    _json_path, md_path = visual_bible_paths(root, session_id)
    if not md_path.exists():
        return ""
    return md_path.read_text(encoding="utf-8")
