"""Render cleaned transcript JSON into deterministic screenplay markdown.

This step formats structured cleaned transcripts into a readable screenplay
draft. It does not rewrite, summarize, embellish, or invent dialogue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

CLEANED_TRANSCRIPTS_DIR = Path("processing") / "cleaned_transcripts"
SCREENPLAY_DIR = Path("processing") / "screenplay"
SCREENPLAY_SESSIONS_PATH = Path("processing") / "metadata" / "screenplay_sessions.json"
CLEAN_SCENE_PATTERN = "escena_*.json"
SCREENPLAY_SCENE_PATTERN = "escena_*.md"
INDEX_FILE_NAME = "screenplay_index.json"

DESCRIPTION_TYPES = {"description"}
DIALOGUE_TYPES = {"dialogue", "npc_dialogue"}
PLAYER_INTENT_TYPES = {"player_intent"}
PLAYER_QUESTION_TYPES = {"player_question"}
MIXED_ENTRY_TYPES = {"mixed_entry"}
EXCLUDED_TYPES = {"rules_meta", "table_talk", "post_session_feedback"}
REVIEW_TYPES = {"unclear"}
SPEAKER_LABELS = {
    "SPEAKER_01": "OLIVIA",
    "SPEAKER_02": "RIVER",
    "SPEAKER_03": "CLARA",
}


@dataclass(frozen=True)
class CleanEntry:
    """One classified cleaned transcript entry."""

    entry_id: int
    line_number: int
    speaker: str | None
    type: str
    text: str
    raw_line: str
    npc_name: str | None


@dataclass(frozen=True)
class CleanScene:
    """One cleaned scene loaded from JSON."""

    scene_id: str
    session_id: str
    entries: list[CleanEntry]


@dataclass(frozen=True)
class RenderedScene:
    """Markdown and counters produced for one scene."""

    scene_id: str
    markdown: str
    descriptions: int
    dialogues: int
    player_intents: int
    player_questions: int
    mixed_entries: int
    review_required: int
    speakers: list[str]


@dataclass(frozen=True)
class ScreenplayResult:
    """Result of a screenplay generation command."""

    scenes: list[RenderedScene]
    skipped: bool
    source_dir: Path
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


def find_latest_session_dir(series_root: Path) -> Path:
    """Find the newest cleaned transcript session directory."""

    cleaned_root = series_root / CLEANED_TRANSCRIPTS_DIR
    if not cleaned_root.is_dir():
        raise FileNotFoundError(f"Cleaned transcripts directory not found: {cleaned_root}")

    candidates = [
        path
        for path in cleaned_root.iterdir()
        if path.is_dir() and any(path.glob(CLEAN_SCENE_PATTERN))
    ]
    if not candidates:
        raise FileNotFoundError(f"No cleaned transcript sessions found in {cleaned_root}")

    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


def resolve_session_dir(series_root: Path, session_name: str | None) -> Path:
    """Resolve a requested cleaned session or choose the newest available."""

    if session_name is None:
        return find_latest_session_dir(series_root)

    session_dir = series_root / CLEANED_TRANSCRIPTS_DIR / session_name
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Cleaned transcript session not found: {session_dir}")
    return session_dir


def list_clean_scene_files(session_dir: Path) -> list[Path]:
    """Return cleaned scene JSON files in deterministic order."""

    scene_files = sorted(session_dir.glob(CLEAN_SCENE_PATTERN))
    if not scene_files:
        raise FileNotFoundError(f"No cleaned scene files found in {session_dir}")
    return scene_files


def sha256_cleaned_session(session_dir: Path) -> str:
    """Hash all cleaned scene files for a session in deterministic order."""

    digest = hashlib.sha256()
    for scene_file in list_clean_scene_files(session_dir):
        digest.update(scene_file.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(scene_file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def relative_to_series(path: Path, series_root: Path) -> str:
    """Return a stable POSIX-style path relative to the series root."""

    return path.resolve().relative_to(series_root.resolve()).as_posix()


def load_registry(metadata_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load screenplay metadata, tolerating a missing file."""

    if not metadata_path.exists():
        return {"sessions": []}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    sessions = data.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError(f"Invalid screenplay sessions metadata: {metadata_path}")
    return {"sessions": sessions}


def write_registry(metadata_path: Path, registry: dict[str, list[dict[str, Any]]]) -> None:
    """Persist screenplay metadata as private pipeline state."""

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def has_processed_sha(registry: dict[str, list[dict[str, Any]]], source_sha256: str) -> bool:
    """Return true when the exact cleaned inputs were already rendered."""

    return any(session.get("sha256") == source_sha256 for session in registry["sessions"])


def load_clean_scene(path: Path) -> CleanScene:
    """Load one cleaned scene JSON file."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = [
        CleanEntry(
            entry_id=int(entry["entry_id"]),
            line_number=int(entry["line_number"]),
            speaker=entry.get("speaker"),
            type=str(entry["type"]),
            text=str(entry["text"]),
            raw_line=str(entry["raw_line"]),
            npc_name=entry.get("npc_name"),
        )
        for entry in payload["entries"]
    ]
    return CleanScene(
        scene_id=str(payload["scene_id"]),
        session_id=str(payload["session_id"]),
        entries=entries,
    )


def character_name(entry: CleanEntry) -> str:
    """Return the screenplay character label for a dialogue entry."""

    if entry.type == "npc_dialogue":
        return (entry.npc_name or "UNKNOWN_NPC").upper()
    if entry.speaker is None:
        return "UNKNOWN_SPEAKER"
    return SPEAKER_LABELS.get(entry.speaker, entry.speaker).upper()


def render_description_section(entries: list[CleanEntry]) -> list[str]:
    """Render description entries as narrative paragraphs."""

    lines = ["## DESCRIPTION", ""]
    if not entries:
        lines.append("_No description entries._")
        return lines

    for entry in entries:
        lines.extend([entry.text, ""])
    return lines


def render_dialogue_section(entries: list[CleanEntry]) -> list[str]:
    """Render dialogue entries in simple screenplay form."""

    lines = ["## DIALOGUE", ""]
    if not entries:
        lines.append("_No dialogue entries._")
        return lines

    for entry in entries:
        lines.extend([character_name(entry), entry.text, ""])
    return lines


def render_review_section(entries: list[CleanEntry]) -> list[str]:
    """Render unclear entries for manual review."""

    if not entries:
        return []

    lines = ["## REVIEW_REQUIRED", ""]
    for entry in entries:
        speaker = entry.speaker or "UNKNOWN_SPEAKER"
        lines.extend([f"[{speaker}]", entry.text, ""])
    return lines


def render_trace_section(title: str, entries: list[CleanEntry]) -> list[str]:
    """Render non-screenplay traceability sections."""

    if not entries:
        return []

    lines = [f"## {title}", ""]
    for entry in entries:
        speaker = entry.speaker or "UNKNOWN_SPEAKER"
        lines.extend([f"[{speaker}]", entry.text, ""])
    return lines


def render_scene(scene: CleanScene) -> RenderedScene:
    """Render one cleaned scene into markdown and counters."""

    descriptions = [entry for entry in scene.entries if entry.type in DESCRIPTION_TYPES]
    dialogues = [entry for entry in scene.entries if entry.type in DIALOGUE_TYPES]
    player_intents = [entry for entry in scene.entries if entry.type in PLAYER_INTENT_TYPES]
    player_questions = [entry for entry in scene.entries if entry.type in PLAYER_QUESTION_TYPES]
    mixed_entries = [entry for entry in scene.entries if entry.type in MIXED_ENTRY_TYPES]
    review_entries = [entry for entry in scene.entries if entry.type in REVIEW_TYPES]
    speakers = sorted(
        {
            character_name(entry)
            for entry in dialogues
            if entry.type in DIALOGUE_TYPES
        }
    )

    lines = [
        f"# {scene.scene_id.replace('_', ' ').upper()}",
        "",
        *render_description_section(descriptions),
        "",
        *render_dialogue_section(dialogues),
    ]
    review_section = render_review_section(review_entries)
    intent_section = render_trace_section("PLAYER_INTENT", player_intents)
    question_section = render_trace_section("PLAYER_QUESTION", player_questions)
    mixed_section = render_trace_section("MIXED_ENTRIES", mixed_entries)
    if intent_section:
        lines.extend(["", *intent_section])
    if question_section:
        lines.extend(["", *question_section])
    if mixed_section:
        lines.extend(["", *mixed_section])
    if review_section:
        lines.extend(["", *review_section])

    markdown = "\n".join(lines).rstrip() + "\n"
    return RenderedScene(
        scene_id=scene.scene_id,
        markdown=markdown,
        descriptions=len(descriptions),
        dialogues=len(dialogues),
        player_intents=len(player_intents),
        player_questions=len(player_questions),
        mixed_entries=len(mixed_entries),
        review_required=len(review_entries),
        speakers=speakers,
    )


def clear_previous_outputs(output_dir: Path) -> None:
    """Remove previous generated screenplay files for one session."""

    for scene_file in output_dir.glob(SCREENPLAY_SCENE_PATTERN):
        scene_file.unlink()
    index_file = output_dir / INDEX_FILE_NAME
    if index_file.exists():
        index_file.unlink()


def write_screenplay_files(scenes: list[RenderedScene], output_dir: Path) -> None:
    """Write rendered markdown scene files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_outputs(output_dir)
    for scene in scenes:
        (output_dir / f"{scene.scene_id}.md").write_text(scene.markdown, encoding="utf-8")


def aggregate_speakers(scenes: list[RenderedScene]) -> list[str]:
    """Return sorted speakers used in the screenplay dialogue sections."""

    return sorted({speaker for scene in scenes for speaker in scene.speakers})


def write_screenplay_index(
    session_id: str,
    scenes: list[RenderedScene],
    output_dir: Path,
) -> None:
    """Write screenplay_index.json with aggregate counters."""

    payload = {
        "session_id": session_id,
        "total_scenes": len(scenes),
        "total_dialogues": sum(scene.dialogues for scene in scenes),
        "total_descriptions": sum(scene.descriptions for scene in scenes),
        "total_player_intents": sum(scene.player_intents for scene in scenes),
        "total_player_questions": sum(scene.player_questions for scene in scenes),
        "total_mixed_entries": sum(scene.mixed_entries for scene in scenes),
        "total_review_required": sum(scene.review_required for scene in scenes),
        "speakers": aggregate_speakers(scenes),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "dialogues": scene.dialogues,
                "descriptions": scene.descriptions,
                "player_intents": scene.player_intents,
                "player_questions": scene.player_questions,
                "mixed_entries": scene.mixed_entries,
                "review_required": scene.review_required,
                "speakers": scene.speakers,
            }
            for scene in scenes
        ],
    }
    (output_dir / INDEX_FILE_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def record_screenplay_session(
    registry: dict[str, list[dict[str, Any]]],
    *,
    session_id: str,
    source_path: str,
    source_sha256: str,
    output_dir: str,
    scenes: list[RenderedScene],
) -> None:
    """Insert or replace metadata for one screenplay session."""

    sessions = [
        session
        for session in registry["sessions"]
        if session.get("source_path") != source_path
    ]
    sessions.append(
        {
            "session_id": session_id,
            "source_path": source_path,
            "sha256": source_sha256,
            "processed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "output_dir": output_dir,
            "total_scenes": len(scenes),
            "total_dialogues": sum(scene.dialogues for scene in scenes),
            "total_descriptions": sum(scene.descriptions for scene in scenes),
            "total_player_intents": sum(scene.player_intents for scene in scenes),
            "total_player_questions": sum(scene.player_questions for scene in scenes),
            "total_mixed_entries": sum(scene.mixed_entries for scene in scenes),
            "total_review_required": sum(scene.review_required for scene in scenes),
        }
    )
    registry["sessions"] = sorted(sessions, key=lambda session: session["source_path"])


def build_screenplay(
    series_name: str,
    session_name: str | None = None,
    *,
    force: bool = False,
) -> ScreenplayResult:
    """Build screenplay markdown for one cleaned transcript session."""

    project_root = get_project_root()
    series_root = resolve_series_root(project_root, series_name)
    session_dir = resolve_session_dir(series_root, session_name)
    session_id = session_dir.name
    output_dir = series_root / SCREENPLAY_DIR / session_id
    metadata_path = series_root / SCREENPLAY_SESSIONS_PATH
    source_sha256 = sha256_cleaned_session(session_dir)
    registry = load_registry(metadata_path)

    if has_processed_sha(registry, source_sha256) and not force:
        print("Screenplay already generated. Use --force to regenerate.")
        return ScreenplayResult(scenes=[], skipped=True, source_dir=session_dir, output_dir=output_dir)

    LOGGER.info("Series: %s", series_name)
    LOGGER.info("Building screenplay from: %s", session_dir)
    clean_scenes = [load_clean_scene(path) for path in list_clean_scene_files(session_dir)]
    rendered_scenes = [render_scene(scene) for scene in clean_scenes]

    LOGGER.info("Writing %s screenplay scenes to: %s", len(rendered_scenes), output_dir)
    write_screenplay_files(rendered_scenes, output_dir)
    write_screenplay_index(session_id, rendered_scenes, output_dir)
    record_screenplay_session(
        registry,
        session_id=session_id,
        source_path=relative_to_series(session_dir, series_root),
        source_sha256=source_sha256,
        output_dir=relative_to_series(output_dir, series_root),
        scenes=rendered_scenes,
    )
    write_registry(metadata_path, registry)

    return ScreenplayResult(
        scenes=rendered_scenes,
        skipped=False,
        source_dir=session_dir,
        output_dir=output_dir,
    )


def summarize(scenes: list[RenderedScene]) -> str:
    """Build a concise human-readable summary for CLI output."""

    counters = Counter(
        {
            "scenes": len(scenes),
            "dialogues": sum(scene.dialogues for scene in scenes),
            "descriptions": sum(scene.descriptions for scene in scenes),
            "player_intents": sum(scene.player_intents for scene in scenes),
            "player_questions": sum(scene.player_questions for scene in scenes),
            "mixed_entries": sum(scene.mixed_entries for scene in scenes),
            "review_required": sum(scene.review_required for scene in scenes),
        }
    )
    return "\n".join(
        [
            f"Escenas de guion: {counters['scenes']}",
            f"Dialogos incluidos: {counters['dialogues']}",
            f"Descripciones incluidas: {counters['descriptions']}",
            f"Intenciones de jugador: {counters['player_intents']}",
            f"Preguntas de jugador: {counters['player_questions']}",
            f"Entradas mixtas: {counters['mixed_entries']}",
            f"Entradas para revision: {counters['review_required']}",
            f"Personajes en dialogo: {', '.join(aggregate_speakers(scenes)) or 'ninguno'}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Render cleaned transcript JSON into screenplay markdown."
    )
    parser.add_argument(
        "--series",
        required=True,
        help="Series directory name, for example La_Frecuencia_Bauman.",
    )
    parser.add_argument(
        "--session",
        default=None,
        help="Optional cleaned transcript session name. Defaults to the newest session.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate screenplay even if the cleaned input SHA-256 was already rendered.",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    result = build_screenplay(args.series, args.session, force=args.force)
    if not result.skipped:
        print(summarize(result.scenes))


if __name__ == "__main__":
    main()
