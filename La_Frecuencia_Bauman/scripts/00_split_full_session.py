"""Split a full role-playing session transcript into candidate scenes.

This step is intentionally deterministic: it uses only parsing and keyword
heuristics, without LLMs or external AI services. The goal is to preserve the
original transcript while creating coarse scene candidates for later pipeline
steps.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


LOGGER = logging.getLogger(__name__)

SPEAKER_PATTERN = re.compile(r"^(?P<speaker>SPEAKER_\d+):\s*(?P<text>.*)$")
SCENE_FILE_PATTERN = "escena_*.txt"
INDEX_FILE_NAME = "scenes_index.json"
DEFAULT_OUTPUT_DIR = Path("processing") / "scene_candidates"

NARRATOR_SPEAKER = "SPEAKER_00"
MIN_SCENE_LINES = 8
SPLIT_SCORE_THRESHOLD = 2

LOCATION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cafeteria": ("cafeteria", "cafe", "bar", "terraza"),
    "calle": ("calle", "avenida", "acera", "callejon", "plaza"),
    "bosque": ("bosque", "arboles", "sendero", "claro", "montana"),
    "hospital": ("hospital", "clinica", "urgencias", "quirofano"),
    "casa": ("casa", "apartamento", "piso", "habitacion", "salon", "cocina"),
    "carretera": ("carretera", "autopista", "arcen", "vehiculo", "coche"),
    "oficina": ("oficina", "despacho", "sala de reuniones"),
    "comisaria": ("comisaria", "policia", "interrogatorio"),
    "almacen": ("almacen", "nave industrial", "fabrica"),
    "sotano": ("sotano", "subsuelo", "bodega"),
}

TEMPORAL_MARKERS: tuple[str, ...] = (
    "horas despues",
    "mas tarde",
    "esa noche",
    "al dia siguiente",
    "a la manana siguiente",
    "dias despues",
    "semanas despues",
    "un rato despues",
    "poco despues",
    "minutos despues",
)

EVENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "violence": ("disparo", "disparos", "sangre", "golpe", "ataque", "herida"),
    "explosion": ("explosion", "explota", "estalla", "detonacion"),
    "chase": ("persecucion", "persigue", "huida", "corren", "escapan"),
    "entry": ("entra", "aparece", "irrumpe", "llega", "se presenta"),
    "discovery": ("descubre", "descubren", "revela", "encuentra", "hallazgo"),
    "meeting": ("reunion", "se encuentran", "se reunen", "cita", "encuentro"),
}

FOCUS_SHIFT_MARKERS: tuple[str, ...] = (
    "mientras tanto",
    "en otro lugar",
    "por otro lado",
    "cambiamos a",
    "vemos a",
    "la camara sigue",
    "volvemos con",
)


@dataclass(frozen=True)
class TranscriptLine:
    """A parsed transcript line with its original text preserved."""

    line_number: int
    raw: str
    speaker: str | None
    text: str


@dataclass(frozen=True)
class SplitSignal:
    """Heuristic evidence that a line may start a new scene."""

    score: int
    location: str | None = None
    event: str | None = None
    temporal: str | None = None
    focus_shift: bool = False


@dataclass(frozen=True)
class Scene:
    """A candidate scene assembled from contiguous transcript lines."""

    scene_id: str
    lines: list[TranscriptLine]
    detected_location: str | None
    detected_event: str | None

    @property
    def start_line(self) -> int:
        return self.lines[0].line_number

    @property
    def end_line(self) -> int:
        return self.lines[-1].line_number

    @property
    def characters(self) -> list[str]:
        speakers = {
            line.speaker
            for line in self.lines
            if line.speaker is not None and line.speaker != NARRATOR_SPEAKER
        }
        return sorted(speakers)


def normalize_text(text: str) -> str:
    """Return lowercase ASCII-ish text for accent-insensitive matching."""

    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def parse_transcript(raw_text: str) -> list[TranscriptLine]:
    """Parse speaker-prefixed transcript lines while preserving all content."""

    parsed_lines: list[TranscriptLine] = []
    for index, raw_line in enumerate(raw_text.splitlines()):
        # Some Windows tools write UTF-8 with BOM. Match against a cleaned view
        # while keeping raw untouched so no transcript content is lost.
        match_line = raw_line.lstrip("\ufeff")
        match = SPEAKER_PATTERN.match(match_line)
        if match:
            parsed_lines.append(
                TranscriptLine(
                    line_number=index,
                    raw=raw_line,
                    speaker=match.group("speaker"),
                    text=match.group("text"),
                )
            )
        else:
            parsed_lines.append(
                TranscriptLine(
                    line_number=index,
                    raw=raw_line,
                    speaker=None,
                    text=raw_line,
                )
            )
    return parsed_lines


def find_location(text: str) -> str | None:
    """Detect a coarse location label from configured location keywords."""

    normalized = normalize_text(text)
    for location, keywords in LOCATION_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return location
    return None


def find_temporal_marker(text: str) -> str | None:
    """Detect temporal jumps such as 'mas tarde' or 'al dia siguiente'."""

    normalized = normalize_text(text)
    for marker in TEMPORAL_MARKERS:
        if marker in normalized:
            return marker
    return None


def find_event(text: str) -> str | None:
    """Detect strong narrative events using deterministic keyword groups."""

    normalized = normalize_text(text)
    for event, keywords in EVENT_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return event
    return None


def has_focus_shift(text: str) -> bool:
    """Return true when the narrator appears to switch narrative focus."""

    normalized = normalize_text(text)
    return any(marker in normalized for marker in FOCUS_SHIFT_MARKERS)


def detect_split_signal(line: TranscriptLine) -> SplitSignal:
    """Score whether a line contains evidence for a scene boundary.

    Speaker 00 is weighted because this project treats it as the narrator or
    scene director, where location, time, and focus changes are most reliable.
    """

    if line.speaker != NARRATOR_SPEAKER:
        return SplitSignal(score=0)

    location = find_location(line.text)
    temporal = find_temporal_marker(line.text)
    event = find_event(line.text)
    focus_shift = has_focus_shift(line.text)

    score = 0
    if location:
        score += 1
    if temporal:
        score += 2
    if event:
        score += 2
    if focus_shift:
        score += 2

    return SplitSignal(
        score=score,
        location=location,
        event=event,
        temporal=temporal,
        focus_shift=focus_shift,
    )


def should_split_scene(current_scene: list[TranscriptLine], signal: SplitSignal) -> bool:
    """Decide whether a signal is strong enough to start a new scene."""

    if len(current_scene) < MIN_SCENE_LINES:
        return False
    return signal.score >= SPLIT_SCORE_THRESHOLD


def most_recent_label(labels: Iterable[str | None]) -> str | None:
    """Return the last non-empty detected label from a sequence."""

    for label in reversed(list(labels)):
        if label:
            return label
    return None


def build_scene(scene_number: int, lines: list[TranscriptLine]) -> Scene:
    """Create scene metadata from a list of transcript lines."""

    locations = [find_location(line.text) for line in lines if line.speaker == NARRATOR_SPEAKER]
    events = [find_event(line.text) for line in lines if line.speaker == NARRATOR_SPEAKER]
    return Scene(
        scene_id=f"escena_{scene_number:03d}",
        lines=lines,
        detected_location=most_recent_label(locations),
        detected_event=most_recent_label(events),
    )


def split_into_scenes(lines: list[TranscriptLine]) -> list[Scene]:
    """Split parsed transcript lines into deterministic candidate scenes."""

    if not lines:
        return []

    scenes: list[Scene] = []
    current_scene: list[TranscriptLine] = []

    for line in lines:
        signal = detect_split_signal(line)
        if current_scene and should_split_scene(current_scene, signal):
            scenes.append(build_scene(len(scenes) + 1, current_scene))
            current_scene = []
        current_scene.append(line)

    if current_scene:
        scenes.append(build_scene(len(scenes) + 1, current_scene))

    return scenes


def detect_series_root(input_path: Path) -> Path:
    """Infer the series root from an input transcript path."""

    resolved_input = input_path.resolve()
    for parent in resolved_input.parents:
        if (parent / "input").is_dir() and (parent / "processing").is_dir():
            return parent
    return Path.cwd().resolve()


def clear_previous_scene_outputs(output_dir: Path) -> None:
    """Remove previous generated scene files from the scene candidate folder."""

    for scene_file in output_dir.glob(SCENE_FILE_PATTERN):
        scene_file.unlink()
    index_file = output_dir / INDEX_FILE_NAME
    if index_file.exists():
        index_file.unlink()


def write_scene_files(scenes: list[Scene], output_dir: Path) -> None:
    """Write scene transcript files with original lines intact."""

    output_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_scene_outputs(output_dir)
    for scene in scenes:
        scene_text = "\n".join(line.raw for line in scene.lines)
        (output_dir / f"{scene.scene_id}.txt").write_text(
            scene_text + "\n",
            encoding="utf-8",
        )


def scene_to_index_entry(scene: Scene) -> dict[str, object]:
    """Convert scene metadata to the JSON index format."""

    return {
        "scene_id": scene.scene_id,
        "start_line": scene.start_line,
        "end_line": scene.end_line,
        "detected_location": scene.detected_location,
        "detected_event": scene.detected_event,
        "characters": scene.characters,
    }


def write_index(session_name: str, scenes: list[Scene], output_dir: Path) -> None:
    """Write the scenes_index.json file."""

    payload = {
        "session": session_name,
        "total_scenes": len(scenes),
        "scenes": [scene_to_index_entry(scene) for scene in scenes],
    }
    (output_dir / INDEX_FILE_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def summarize(scenes: list[Scene]) -> str:
    """Build a concise human-readable summary for CLI output."""

    characters = sorted({character for scene in scenes for character in scene.characters})
    locations = sorted(
        {scene.detected_location for scene in scenes if scene.detected_location is not None}
    )
    return "\n".join(
        [
            f"Escenas detectadas: {len(scenes)}",
            f"Personajes detectados: {', '.join(characters) if characters else 'ninguno'}",
            f"Posibles localizaciones: {', '.join(locations) if locations else 'ninguna'}",
        ]
    )


def split_session(input_path: Path, output_dir: Path | None = None) -> list[Scene]:
    """Read a transcript, split it, and write scene candidate outputs."""

    if not input_path.exists():
        raise FileNotFoundError(f"Transcript not found: {input_path}")

    session_name = input_path.stem
    series_root = detect_series_root(input_path)
    target_output_dir = output_dir or series_root / DEFAULT_OUTPUT_DIR

    LOGGER.info("Reading transcript: %s", input_path)
    raw_text = input_path.read_text(encoding="utf-8")
    lines = parse_transcript(raw_text)
    scenes = split_into_scenes(lines)

    LOGGER.info("Writing %s scene candidates to: %s", len(scenes), target_output_dir)
    write_scene_files(scenes, target_output_dir)
    write_index(session_name, scenes, target_output_dir)

    return scenes


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Split a full session transcript into candidate scenes."
    )
    parser.add_argument(
        "transcript",
        type=Path,
        help="Path to input/raw_sessions/<session>.txt",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory. Defaults to processing/scene_candidates.",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    scenes = split_session(args.transcript, args.output_dir)
    print(summarize(scenes))


if __name__ == "__main__":
    main()
