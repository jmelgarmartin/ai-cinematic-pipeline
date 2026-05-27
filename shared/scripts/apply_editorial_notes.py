"""Apply human editorial notes to screenplay markdown without rewriting text.

This stage is deterministic and traceable. It reads screenplay markdown files,
optionally reads matching editorial notes, and writes annotated JSON for later
editorial or LLM-assisted stages. It does not modify the source screenplay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

SCREENPLAY_DIR = Path("processing") / "screenplay"
EDITORIAL_NOTES_DIR = Path("editorial_notes")
ANNOTATED_SCREENPLAY_DIR = Path("processing") / "annotated_screenplay"
ANNOTATED_SESSIONS_PATH = Path("processing") / "metadata" / "annotated_sessions.json"
SCREENPLAY_SCENE_PATTERN = "escena_*.md"
ANNOTATED_SCENE_PATTERN = "escena_*.annotated.json"
INDEX_FILE_NAME = "annotated_index.json"
EMPTY_NOTES_SHA256 = hashlib.sha256(b"").hexdigest()

NOTES_SECTION_MAP = {
    "eliminar": "remove",
    "mantener": "keep",
    "planos sugeridos": "suggested_shots",
    "intencion": "intention",
    "intención": "intention",
}
LIST_NOTE_KEYS = {"remove", "keep", "suggested_shots"}


@dataclass(frozen=True)
class EditorialNotes:
    """Parsed editorial notes for one scene."""

    remove: list[str]
    keep: list[str]
    suggested_shots: list[str]
    intention: str


@dataclass(frozen=True)
class AnnotatedScene:
    """One screenplay scene plus optional human notes."""

    scene_id: str
    source_screenplay_file: str
    editorial_notes_file: str
    screenplay_sha256: str
    notes_sha256: str
    screenplay_markdown: str
    editorial_notes: EditorialNotes
    status: str


@dataclass(frozen=True)
class AnnotationResult:
    """Result of an annotation command, including idempotent skip state."""

    scenes: list[AnnotatedScene]
    skipped: bool
    source_dir: Path
    notes_dir: Path
    output_dir: Path


def get_project_root() -> Path:
    """Resolve the project root from this global script location."""

    return Path(__file__).resolve().parents[2]


def resolve_series_root(project_root: Path, series_name: str) -> Path:
    """Resolve and validate a series root directory."""

    series_root = project_root / series_name
    if not series_root.is_dir():
        raise FileNotFoundError(f"Series not found: {series_root}")
    return series_root


def resolve_screenplay_session(series_root: Path, session_name: str) -> Path:
    """Resolve a screenplay session directory."""

    session_dir = series_root / SCREENPLAY_DIR / session_name
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Screenplay session not found: {session_dir}")
    return session_dir


def list_screenplay_files(session_dir: Path) -> list[Path]:
    """Return screenplay scene files in deterministic order."""

    scene_files = sorted(session_dir.glob(SCREENPLAY_SCENE_PATTERN))
    if not scene_files:
        raise FileNotFoundError(f"No screenplay scene files found in {session_dir}")
    return scene_files


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hash of one file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_optional_file(path: Path) -> str:
    """Return the SHA-256 hash for a notes file, or the empty-content hash."""

    if not path.exists():
        return EMPTY_NOTES_SHA256
    return sha256_file(path)


def sha256_annotation_inputs(screenplay_dir: Path, notes_dir: Path) -> str:
    """Hash screenplay files and matching notes in deterministic order."""

    digest = hashlib.sha256()
    for screenplay_file in list_screenplay_files(screenplay_dir):
        notes_file = notes_dir / f"{screenplay_file.stem}.notes.md"
        digest.update(screenplay_file.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(screenplay_file.read_bytes())
        digest.update(b"\0")
        digest.update(notes_file.name.encode("utf-8"))
        digest.update(b"\0")
        if notes_file.exists():
            digest.update(notes_file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def relative_to_series(path: Path, series_root: Path) -> str:
    """Return a stable POSIX-style path relative to the series root."""

    return path.resolve().relative_to(series_root.resolve()).as_posix()


def normalize_heading(heading: str) -> str:
    """Normalize a markdown heading into a known editorial notes key."""

    return heading.strip().strip("#").strip().lower()


def append_note(notes: dict[str, list[str] | str], key: str, value: str) -> None:
    """Append parsed note text to the right section."""

    text = value.strip()
    if not text:
        return
    if key in LIST_NOTE_KEYS:
        note_list = notes[key]
        if isinstance(note_list, list):
            note_list.append(text)
        return
    if key == "intention":
        current = notes[key]
        notes[key] = f"{current}\n{text}".strip() if isinstance(current, str) else text


def parse_editorial_notes(path: Path) -> EditorialNotes:
    """Parse the supported markdown note sections for one scene."""

    notes: dict[str, list[str] | str] = {
        "remove": [],
        "keep": [],
        "suggested_shots": [],
        "intention": "",
    }
    if not path.exists():
        return EditorialNotes(remove=[], keep=[], suggested_shots=[], intention="")

    current_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            current_key = NOTES_SECTION_MAP.get(normalize_heading(stripped))
            continue
        if stripped.startswith("# "):
            continue
        if current_key is None:
            continue
        value = stripped[2:].strip() if stripped.startswith("- ") else stripped
        append_note(notes, current_key, value)

    return EditorialNotes(
        remove=list(notes["remove"]) if isinstance(notes["remove"], list) else [],
        keep=list(notes["keep"]) if isinstance(notes["keep"], list) else [],
        suggested_shots=list(notes["suggested_shots"])
        if isinstance(notes["suggested_shots"], list)
        else [],
        intention=str(notes["intention"]),
    )


def load_registry(metadata_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load annotation metadata, tolerating a missing file."""

    if not metadata_path.exists():
        return {"sessions": []}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    sessions = data.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError(f"Invalid annotation sessions metadata: {metadata_path}")
    return {"sessions": sessions}


def write_registry(metadata_path: Path, registry: dict[str, list[dict[str, Any]]]) -> None:
    """Persist annotation metadata as private pipeline state."""

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def has_processed_sha(registry: dict[str, list[dict[str, Any]]], source_sha256: str) -> bool:
    """Return true when the exact screenplay and notes inputs were annotated."""

    return any(session.get("sha256") == source_sha256 for session in registry["sessions"])


def build_annotated_scene(
    screenplay_file: Path,
    notes_file: Path,
    series_root: Path,
) -> AnnotatedScene:
    """Build one annotated scene payload from screenplay and optional notes."""

    scene_id = screenplay_file.stem
    return AnnotatedScene(
        scene_id=scene_id,
        source_screenplay_file=relative_to_series(screenplay_file, series_root),
        editorial_notes_file=relative_to_series(notes_file, series_root),
        screenplay_sha256=sha256_file(screenplay_file),
        notes_sha256=sha256_optional_file(notes_file),
        screenplay_markdown=screenplay_file.read_text(encoding="utf-8"),
        editorial_notes=parse_editorial_notes(notes_file),
        status="annotated",
    )


def notes_to_payload(notes: EditorialNotes) -> dict[str, object]:
    """Convert editorial notes to JSON payload."""

    return {
        "remove": notes.remove,
        "keep": notes.keep,
        "suggested_shots": notes.suggested_shots,
        "intention": notes.intention,
    }


def scene_to_payload(scene: AnnotatedScene) -> dict[str, object]:
    """Convert an annotated scene to JSON payload."""

    return {
        "scene_id": scene.scene_id,
        "source_screenplay_file": scene.source_screenplay_file,
        "editorial_notes_file": scene.editorial_notes_file,
        "hashes": {
            "screenplay_sha256": scene.screenplay_sha256,
            "notes_sha256": scene.notes_sha256,
        },
        "screenplay_markdown": scene.screenplay_markdown,
        "editorial_notes": notes_to_payload(scene.editorial_notes),
        "status": scene.status,
    }


def clear_previous_outputs(output_dir: Path) -> None:
    """Remove previous generated annotation files for one session."""

    for scene_file in output_dir.glob(ANNOTATED_SCENE_PATTERN):
        scene_file.unlink()
    index_file = output_dir / INDEX_FILE_NAME
    if index_file.exists():
        index_file.unlink()


def write_annotated_scenes(scenes: list[AnnotatedScene], output_dir: Path) -> None:
    """Write one annotated JSON file per scene."""

    output_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_outputs(output_dir)
    for scene in scenes:
        (output_dir / f"{scene.scene_id}.annotated.json").write_text(
            json.dumps(scene_to_payload(scene), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def write_annotated_index(
    session_id: str,
    scenes: list[AnnotatedScene],
    output_dir: Path,
) -> None:
    """Write the annotated_index.json summary file."""

    payload = {
        "session_id": session_id,
        "total_scenes": len(scenes),
        "scenes_with_notes": sum(
            1 for scene in scenes if scene.notes_sha256 != EMPTY_NOTES_SHA256
        ),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "source_screenplay_file": scene.source_screenplay_file,
                "editorial_notes_file": scene.editorial_notes_file,
                "has_notes": scene.notes_sha256 != EMPTY_NOTES_SHA256,
                "status": scene.status,
                "hashes": {
                    "screenplay_sha256": scene.screenplay_sha256,
                    "notes_sha256": scene.notes_sha256,
                },
            }
            for scene in scenes
        ],
    }
    (output_dir / INDEX_FILE_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def record_annotation_session(
    registry: dict[str, list[dict[str, Any]]],
    *,
    session_id: str,
    source_path: str,
    notes_path: str,
    source_sha256: str,
    output_dir: str,
    scenes: list[AnnotatedScene],
) -> None:
    """Insert or replace metadata for one annotated screenplay session."""

    sessions = [
        session
        for session in registry["sessions"]
        if session.get("source_path") != source_path
    ]
    sessions.append(
        {
            "session_id": session_id,
            "source_path": source_path,
            "notes_path": notes_path,
            "sha256": source_sha256,
            "processed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "output_dir": output_dir,
            "total_scenes": len(scenes),
            "scenes_with_notes": sum(
                1 for scene in scenes if scene.notes_sha256 != EMPTY_NOTES_SHA256
            ),
        }
    )
    registry["sessions"] = sorted(sessions, key=lambda session: session["source_path"])


def apply_editorial_notes(
    series_name: str,
    session_name: str,
    *,
    force: bool = False,
) -> AnnotationResult:
    """Apply optional editorial notes to one screenplay session."""

    project_root = get_project_root()
    series_root = resolve_series_root(project_root, series_name)
    screenplay_dir = resolve_screenplay_session(series_root, session_name)
    notes_dir = series_root / EDITORIAL_NOTES_DIR / session_name
    output_dir = series_root / ANNOTATED_SCREENPLAY_DIR / session_name
    metadata_path = series_root / ANNOTATED_SESSIONS_PATH
    source_sha256 = sha256_annotation_inputs(screenplay_dir, notes_dir)
    registry = load_registry(metadata_path)

    if has_processed_sha(registry, source_sha256) and not force:
        print("Annotated screenplay already generated. Use --force to regenerate.")
        return AnnotationResult(
            scenes=[],
            skipped=True,
            source_dir=screenplay_dir,
            notes_dir=notes_dir,
            output_dir=output_dir,
        )

    LOGGER.info("Series: %s", series_name)
    LOGGER.info("Applying editorial notes to: %s", screenplay_dir)
    if not notes_dir.exists():
        LOGGER.info("Editorial notes directory not found; generating empty notes.")

    scenes = [
        build_annotated_scene(
            screenplay_file,
            notes_dir / f"{screenplay_file.stem}.notes.md",
            series_root,
        )
        for screenplay_file in list_screenplay_files(screenplay_dir)
    ]

    LOGGER.info("Writing %s annotated scenes to: %s", len(scenes), output_dir)
    write_annotated_scenes(scenes, output_dir)
    write_annotated_index(session_name, scenes, output_dir)
    record_annotation_session(
        registry,
        session_id=session_name,
        source_path=relative_to_series(screenplay_dir, series_root),
        notes_path=relative_to_series(notes_dir, series_root),
        source_sha256=source_sha256,
        output_dir=relative_to_series(output_dir, series_root),
        scenes=scenes,
    )
    write_registry(metadata_path, registry)

    return AnnotationResult(
        scenes=scenes,
        skipped=False,
        source_dir=screenplay_dir,
        notes_dir=notes_dir,
        output_dir=output_dir,
    )


def summarize(scenes: list[AnnotatedScene]) -> str:
    """Build a concise human-readable summary for CLI output."""

    scenes_with_notes = sum(1 for scene in scenes if scene.notes_sha256 != EMPTY_NOTES_SHA256)
    return "\n".join(
        [
            f"Escenas anotadas: {len(scenes)}",
            f"Escenas con notas: {scenes_with_notes}",
            f"Escenas sin notas: {len(scenes) - scenes_with_notes}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Apply optional human editorial notes to screenplay markdown."
    )
    parser.add_argument(
        "--series",
        required=True,
        help="Series directory name, for example La_Frecuencia_Bauman.",
    )
    parser.add_argument(
        "--session",
        required=True,
        help="Screenplay session name to annotate.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate annotated JSON even if screenplay and notes hashes match.",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    result = apply_editorial_notes(args.series, args.session, force=args.force)
    if not result.skipped:
        print(summarize(result.scenes))


if __name__ == "__main__":
    main()
