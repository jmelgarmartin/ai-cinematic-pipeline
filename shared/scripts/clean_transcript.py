"""Classify candidate scene transcripts into structured cleaned entries.

This step is deterministic and conservative: it does not remove, rewrite, or
summarize transcript text. It parses each scene candidate, classifies each line
with heuristics, and writes structured JSON for later pipeline stages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import string
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger(__name__)

SPEAKER_PATTERN = re.compile(r"^(?P<speaker>SPEAKER_\d+):\s*(?P<text>.*)$")
SCENE_FILE_PATTERN = "escena_*.txt"
CLEAN_SCENE_PATTERN = "escena_*.json"
INDEX_FILE_NAME = "clean_index.json"
SCENE_CANDIDATES_DIR = Path("processing") / "scene_candidates"
CLEANED_TRANSCRIPTS_DIR = Path("processing") / "cleaned_transcripts"
CLEANED_SESSIONS_PATH = Path("processing") / "metadata" / "cleaned_sessions.json"

NARRATOR_SPEAKER = "SPEAKER_00"
ENTRY_TYPES = (
    "description",
    "dialogue",
    "npc_dialogue",
    "player_intent",
    "player_question",
    "rules_meta",
    "table_talk",
    "post_session_feedback",
    "mixed_entry",
    "unclear",
)

NPC_NAME_PATTERN = r"(?:[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÜÑáéíóúüñ'-]*|el|la|los|las)(?:\s+(?:[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÜÑáéíóúüñ'-]*|hombre|mujer|niño|niña|camarera|camarero|doctor|doctora|agente|policía|policia|anciano|anciana|joven|guardia))*"
NPC_VERBS = (
    "dice",
    "responde",
    "contesta",
    "susurra",
    "grita",
    "murmura",
    "exclama",
    "añade",
    "anade",
    "replica",
)
NPC_STYLE_DIRECT_PATTERN = re.compile(
    rf"^(?P<npc>{NPC_NAME_PATTERN})\s*:\s*(?P<dialogue>.+)$"
)
NPC_ATTRIBUTION_PATTERN = re.compile(
    rf"^(?P<npc>{NPC_NAME_PATTERN})\s+(?:os\s+mira\s+y\s+)?"
    rf"(?P<verb>{'|'.join(NPC_VERBS)})\s*:?\s*(?P<dialogue>.+)$",
)
NPC_QUOTED_PATTERN = re.compile(
    rf"^(?P<npc>{NPC_NAME_PATTERN})\s+(?:os\s+mira\s+y\s+)?"
    rf"(?P<verb>{'|'.join(NPC_VERBS)})\s*:?\s*[\"“](?P<dialogue>.+?)[\"”]\s*$",
)

RULES_PATTERNS = (
    re.compile(r"\b\d+d\d+\b", re.IGNORECASE),
    re.compile(r"\bhaz una tirada\b", re.IGNORECASE),
    re.compile(r"\bhacer una tirada\b", re.IGNORECASE),
    re.compile(r"\btiradas? de\b", re.IGNORECASE),
    re.compile(r"\bsaco un \d+\b", re.IGNORECASE),
    re.compile(r"\bhe sacado \d+\b", re.IGNORECASE),
    re.compile(r"\bdificultad\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bdados?\b", re.IGNORECASE),
    re.compile(r"\bgastar afortunad[oa]\b", re.IGNORECASE),
    re.compile(r"\btengo ventaja\b", re.IGNORECASE),
    re.compile(r"\bpuedo gastar\b", re.IGNORECASE),
    re.compile(r"\bexito parcial\b", re.IGNORECASE),
    re.compile(r"\bsiete y uno\b", re.IGNORECASE),
)

POST_SESSION_FEEDBACK_MARKERS = (
    "me ha gustado",
    "me gusto",
    "mi deseo",
    "ver la partida",
    "ver el capitulo",
    "dure el capitulo",
    "retencion",
    "darkon",
    "estrellas",
    "deseos",
    "post partida",
    "postpartida",
)

POST_SESSION_CONTEXT_MARKERS = (
    "como personaje",
    "proxima sesion",
    "entre sesiones",
    "estrellas y deseos",
    "hay que ver el capitulo",
    "cuando vuelva a ver la partida",
)

PLAYER_QUESTION_MARKERS = (
    "que haceis",
    "que haces",
    "como reaccionais",
    "como reaccionas",
    "que vais a hacer",
    "que quieres hacer",
    "decidme que",
    "a quien vemos",
    "a quien nos encontramos",
    "quien nos encontramos",
    "describete",
    "cuentanos",
)

RULES_MARKERS = (
    "percepcion",
    "persuasion",
    "investigacion",
    "afortunado",
    "ventaja",
    "dificultad",
    "tirada",
)

TABLE_TALK_MARKERS = (
    "regla",
    "manual",
    "perdon",
    "espera",
    "un segundo",
    "fuera de personaje",
    "off rol",
    "off-role",
    "micro",
    "discord",
    "se oye",
    "no te escucho",
    "puedo repetir",
    "me he perdido",
    "que guapo",
    "vaya te jodes",
    "en fin",
    "jajaja",
    "jeje",
)

TABLE_TALK_EXACT = (
    "vale",
    "ok",
    "okay",
    "vale ok",
    "vale, ok",
    "perfecto",
    "claro",
    "si",
    "no",
    "si si",
    "no no",
    "en fin",
    "a ver",
)

PLAYER_INTENT_MARKERS = (
    "voy a",
    "voy para alla",
    "vamos a volver",
    "intento",
    "quiero",
    "me acerco",
    "me alejo",
    "saco ",
    "cojo",
    "coge",
    "agarro",
    "miro",
    "busco",
    "reviso",
    "hago algunas fotos",
    "le enseno",
    "le ense",
    "le ayudo",
    "la ayudo",
    "lo ayudo",
    "llamo",
    "salgo",
    "entro",
    "corro",
    "me escondo",
    "lo intenta",
    "intenta abrir",
    "va a cachear",
    "voy a cachear",
    "me llevo",
    "lo dejo",
    "dejo el",
    "dejo la",
    "se lo comento",
    "y corro",
    "taponar",
    "tranquilizarla",
    "hacerle una foto",
    "y despacio",
)

DIALOGUE_MARKERS = (
    "no me gusta",
    "tenemos que",
    "quien eres",
    "quién eres",
    "necesito",
    "ayuda",
    "ayudame",
    "ayúdame",
    "tranquila",
    "tranquilo",
    "ven",
    "sal de aqui",
    "sal de aquí",
    "no pasa nada",
    "cuidado",
)

DESCRIPTION_MARKERS = (
    "vemos a",
    "se ve",
    "lleva",
    "tiene",
    "viste",
    "pelo",
    "ojeras",
    "mirada",
    "entra",
    "sale",
    "camina",
    "mira",
    "sonrie",
    "aparece",
    "la camara",
    "plano",
    "es una sala",
    "sala muy grande",
    "habitacion",
    "persianas",
    "la mesa",
    "mesa de",
    "mesa fija",
    "ambiente",
    "disposicion",
    "ordenador",
    "trastos",
    "caja fuerte",
    "lavadora",
    "ropa sucia",
    "bolsa de ropa",
)

NARRATIVE_MARKERS = (
    "cafeteria",
    "calle",
    "bosque",
    "hospital",
    "casa",
    "comisaria",
    "oficina",
    "habitacion",
    "noche",
    "lluvia",
    "silencio",
    "luz",
    "puerta",
    "ventana",
)

MIXED_ENTRY_NARRATIVE_MARKERS = (
    "dicho esto",
    "se esfuma",
    "apuntando",
    "cuarto",
    "habitacion",
    "lavadora",
    "caja fuerte",
    "cachear",
)

MIXED_ENTRY_INTENT_MARKERS = (
    "voy a",
    "va a",
    "intento",
    "lo dejo",
    "dejo el",
    "cachear",
    "me llevo",
    "apunto",
)

MIXED_ENTRY_SPOKEN_MARKERS = (
    "te sorprenderia",
    "yo creo",
    "me imagino",
    "en plan",
    "claro,",
    "pues yo",
)


@dataclass(frozen=True)
class CandidateLine:
    """One parsed line from a candidate scene file."""

    line_number: int
    raw: str
    speaker: str | None
    text: str


@dataclass(frozen=True)
class CleanEntry:
    """One classified transcript entry."""

    entry_id: int
    line_number: int
    speaker: str | None
    type: str
    text: str
    raw_line: str
    npc_name: str | None = None


@dataclass(frozen=True)
class CleanScene:
    """Structured representation of one cleaned scene."""

    scene_id: str
    session_id: str
    entries: list[CleanEntry]


@dataclass(frozen=True)
class CleanResult:
    """Result of a clean command, including idempotent skip state."""

    scenes: list[CleanScene]
    skipped: bool
    source_dir: Path
    output_dir: Path


def normalize_text(text: str) -> str:
    """Return lowercase accent-insensitive text for heuristic matching."""

    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def contains_any(normalized_text: str, markers: tuple[str, ...]) -> bool:
    """Return true when any configured marker appears in normalized text."""

    return any(marker in normalized_text for marker in markers)


def strip_surrounding_quotes(text: str) -> str:
    """Remove one pair of surrounding dialogue quotes when present."""

    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] in "\"“" and stripped[-1] in "\"”":
        return stripped[1:-1].strip()
    return stripped


def normalize_npc_name(raw_name: str) -> str:
    """Normalize spacing in a detected NPC name without inventing content."""

    return " ".join(raw_name.strip().split())


def is_plausible_npc_name(npc_name: str) -> bool:
    """Reject broad sentence fragments that accidentally match as names."""

    normalized = normalize_text(npc_name)
    words = normalized.split()
    if not words or len(words) > 4:
        return False
    if words[0] in {"os", "yo", "tu", "vosotros", "vosotras", "nosotros", "nosotras"}:
        return False
    if words[0] in {"el", "la", "los", "las"}:
        return len(words) >= 2
    return npc_name[0].isupper()


def is_plausible_dialogue(dialogue: str) -> bool:
    """Return true when extracted NPC dialogue contains real text."""

    return any(char.isalnum() for char in dialogue)


def detect_npc_dialogue(text: str) -> tuple[str | None, str | None]:
    """Detect simple NPC dialogue attribution and optionally extract dialogue."""

    for pattern in (NPC_QUOTED_PATTERN, NPC_ATTRIBUTION_PATTERN, NPC_STYLE_DIRECT_PATTERN):
        match = pattern.match(text.strip())
        if match:
            npc_name = normalize_npc_name(match.group("npc"))
            if not is_plausible_npc_name(npc_name):
                continue
            dialogue = strip_surrounding_quotes(match.group("dialogue"))
            if not is_plausible_dialogue(dialogue):
                continue
            return npc_name, dialogue
    return None, None


def parse_scene_file(path: Path) -> list[CandidateLine]:
    """Parse one scene candidate file while preserving raw lines."""

    lines: list[CandidateLine] = []
    for index, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not raw_line.strip():
            continue
        match_line = raw_line.lstrip("\ufeff")
        match = SPEAKER_PATTERN.match(match_line)
        if match:
            lines.append(
                CandidateLine(
                    line_number=index,
                    raw=raw_line,
                    speaker=match.group("speaker"),
                    text=match.group("text"),
                )
            )
        else:
            lines.append(
                CandidateLine(
                    line_number=index,
                    raw=raw_line,
                    speaker=None,
                    text=raw_line,
                )
            )
    return lines


def is_rules_meta(normalized: str) -> bool:
    """Return true for mechanics, resources, rolls, and rule-facing text."""

    if any(pattern.search(normalized) for pattern in RULES_PATTERNS):
        return True
    return contains_any(normalized, RULES_MARKERS) and (
        "tirada" in normalized
        or "haz " in normalized
        or "saco " in normalized
        or "puedo gastar" in normalized
    )


def is_post_session_feedback(normalized: str) -> bool:
    """Return true for final-session feedback and post-game discussion."""

    if contains_any(normalized, POST_SESSION_FEEDBACK_MARKERS):
        return True
    return contains_any(normalized, POST_SESSION_CONTEXT_MARKERS) and not contains_any(
        normalized,
        NARRATIVE_MARKERS,
    )


def is_player_question(normalized: str) -> bool:
    """Return true for questions about possible actions or GM prompts."""

    if contains_any(normalized, PLAYER_QUESTION_MARKERS) and len(normalized) <= 300:
        return True
    if "?" not in normalized and "¿" not in normalized:
        return False
    if "puedo " in normalized or "puedo hacer" in normalized or "puedo intentar" in normalized:
        return True
    question_starters = (
        "puedo",
        "podria",
        "podría",
        "veo",
        "escucho",
        "hay",
        "consigo",
        "me da tiempo",
        "puedo intentar",
        "puedo hacer",
    )
    stripped = normalized.strip(" ¿?¡!")
    return stripped.startswith(question_starters)


def is_table_talk(normalized: str) -> bool:
    """Return true for short social or non-narrative table chatter."""

    stripped = normalized.strip(" .,!¡¿?")
    compact = stripped.translate(str.maketrans("", "", string.punctuation)).strip()
    if stripped in TABLE_TALK_EXACT:
        return True
    if compact in TABLE_TALK_EXACT:
        return True
    if contains_any(normalized, TABLE_TALK_MARKERS):
        return True
    return len(stripped.split()) <= 3 and stripped in {"vale ok", "ok vale", "muy bien"}


def is_player_intent(normalized: str) -> bool:
    """Return true for player-declared actions, plans, or attempted actions."""

    return contains_any(normalized, PLAYER_INTENT_MARKERS)


def is_description(normalized: str) -> bool:
    """Return true for visual, spatial, atmospheric, or character description."""

    return contains_any(normalized, DESCRIPTION_MARKERS)


def is_mixed_entry(normalized: str) -> bool:
    """Return true for risky multi-mode entries that should not be split yet."""

    words = normalized.split()
    if len(words) < 18:
        return False

    has_narrative = contains_any(normalized, MIXED_ENTRY_NARRATIVE_MARKERS)
    has_intent = contains_any(normalized, MIXED_ENTRY_INTENT_MARKERS)
    has_spoken_or_commentary = contains_any(normalized, MIXED_ENTRY_SPOKEN_MARKERS)
    has_connector = " y " in normalized or " pero " in normalized or " entonces " in normalized

    if "dicho esto" in normalized and has_narrative and has_intent:
        return True

    signals = sum((has_narrative, has_intent, has_spoken_or_commentary))
    return signals >= 2 and has_connector


def is_dialogue(normalized: str) -> bool:
    """Return true only for conservative in-fiction spoken lines."""

    stripped = normalized.strip(" ¿?¡!")
    if not stripped:
        return False
    if contains_any(normalized, DIALOGUE_MARKERS):
        return True
    if normalized.startswith(("\"", "“")):
        return True
    if len(stripped) <= 120 and "?" in normalized:
        return not is_player_question(normalized)
    return False


def classify_line(line: CandidateLine) -> str:
    """Classify a transcript line using deterministic priority heuristics."""

    normalized = normalize_text(line.text)
    if not normalized.strip():
        return "unclear"

    if is_post_session_feedback(normalized):
        return "post_session_feedback"

    if is_rules_meta(normalized):
        return "rules_meta"

    if is_player_question(normalized):
        return "player_question"

    if is_table_talk(normalized):
        return "table_talk"

    if line.speaker == NARRATOR_SPEAKER:
        npc_name, _dialogue = detect_npc_dialogue(line.text)
        if npc_name is not None:
            return "npc_dialogue"

    if is_mixed_entry(normalized):
        return "mixed_entry"

    if line.speaker == NARRATOR_SPEAKER:
        return "description"

    if is_description(normalized):
        return "description"

    if line.speaker is not None and contains_any(normalized, NARRATIVE_MARKERS):
        return "description"

    if is_player_intent(normalized):
        return "player_intent"

    if line.speaker is not None and is_dialogue(normalized):
        return "dialogue"

    return "unclear"


def build_clean_entry(entry_id: int, line: CandidateLine) -> CleanEntry:
    """Build one classified entry while preserving original traceability."""

    entry_type = classify_line(line)
    npc_name: str | None = None
    text = line.text
    if entry_type == "npc_dialogue":
        detected_name, detected_dialogue = detect_npc_dialogue(line.text)
        npc_name = detected_name
        if detected_dialogue:
            text = detected_dialogue

    return CleanEntry(
        entry_id=entry_id,
        line_number=line.line_number,
        speaker=line.speaker,
        type=entry_type,
        text=text,
        raw_line=line.raw,
        npc_name=npc_name,
    )


def clean_scene(scene_path: Path, session_id: str) -> CleanScene:
    """Parse and classify one scene candidate file."""

    entries = [
        build_clean_entry(index, line)
        for index, line in enumerate(parse_scene_file(scene_path), start=1)
    ]
    return CleanScene(scene_id=scene_path.stem, session_id=session_id, entries=entries)


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
    """Find the newest scene-candidate session directory."""

    candidates_root = series_root / SCENE_CANDIDATES_DIR
    if not candidates_root.is_dir():
        raise FileNotFoundError(f"Scene candidates directory not found: {candidates_root}")

    candidates = [
        path
        for path in candidates_root.iterdir()
        if path.is_dir() and any(path.glob(SCENE_FILE_PATTERN))
    ]
    if not candidates:
        raise FileNotFoundError(f"No scene candidate sessions found in {candidates_root}")

    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


def resolve_session_dir(series_root: Path, session_name: str | None) -> Path:
    """Resolve a requested session or choose the newest available session."""

    if session_name is None:
        return find_latest_session_dir(series_root)

    session_dir = series_root / SCENE_CANDIDATES_DIR / session_name
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Scene candidate session not found: {session_dir}")
    return session_dir


def list_scene_files(session_dir: Path) -> list[Path]:
    """Return candidate scene files in deterministic order."""

    scene_files = sorted(session_dir.glob(SCENE_FILE_PATTERN))
    if not scene_files:
        raise FileNotFoundError(f"No scene files found in {session_dir}")
    return scene_files


def sha256_scene_session(session_dir: Path) -> str:
    """Hash all scene files for a session in deterministic order."""

    digest = hashlib.sha256()
    for scene_file in list_scene_files(session_dir):
        digest.update(scene_file.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(scene_file.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def relative_to_series(path: Path, series_root: Path) -> str:
    """Return a stable POSIX-style path relative to the series root."""

    return path.resolve().relative_to(series_root.resolve()).as_posix()


def load_cleaned_sessions(metadata_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load cleaned session metadata, tolerating a missing file."""

    if not metadata_path.exists():
        return {"sessions": []}
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    sessions = data.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError(f"Invalid cleaned sessions metadata: {metadata_path}")
    return {"sessions": sessions}


def write_cleaned_sessions(
    metadata_path: Path,
    registry: dict[str, list[dict[str, Any]]],
) -> None:
    """Persist cleaned session metadata as private pipeline state."""

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def has_cleaned_sha(registry: dict[str, list[dict[str, Any]]], source_sha256: str) -> bool:
    """Return true when the exact scene-candidate contents were already cleaned."""

    return any(session.get("sha256") == source_sha256 for session in registry["sessions"])


def entry_type_distribution(scenes: list[CleanScene]) -> dict[str, int]:
    """Count entries by classification type."""

    counts = Counter(entry.type for scene in scenes for entry in scene.entries)
    return {entry_type: counts.get(entry_type, 0) for entry_type in ENTRY_TYPES}


def detected_speakers(scenes: list[CleanScene]) -> list[str]:
    """Return sorted speaker IDs detected in cleaned scenes."""

    speakers = {
        entry.speaker
        for scene in scenes
        for entry in scene.entries
        if entry.speaker is not None
    }
    return sorted(speakers)


def total_entries(scenes: list[CleanScene]) -> int:
    """Return the total number of entries across scenes."""

    return sum(len(scene.entries) for scene in scenes)


def record_cleaned_session(
    registry: dict[str, list[dict[str, Any]]],
    *,
    session_id: str,
    source_path: str,
    source_sha256: str,
    output_dir: str,
    scenes: list[CleanScene],
) -> None:
    """Insert or replace metadata for one cleaned session."""

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
            "total_entries": total_entries(scenes),
            "type_distribution": entry_type_distribution(scenes),
            "speakers": detected_speakers(scenes),
        }
    )
    registry["sessions"] = sorted(sessions, key=lambda session: session["source_path"])


def entry_to_payload(entry: CleanEntry) -> dict[str, object]:
    """Convert a cleaned entry to JSON payload."""

    return {
        "entry_id": entry.entry_id,
        "line_number": entry.line_number,
        "speaker": entry.speaker,
        "type": entry.type,
        "npc_name": entry.npc_name,
        "text": entry.text,
        "raw_line": entry.raw_line,
    }


def scene_to_payload(scene: CleanScene) -> dict[str, object]:
    """Convert a cleaned scene to JSON payload."""

    return {
        "scene_id": scene.scene_id,
        "session_id": scene.session_id,
        "entries": [entry_to_payload(entry) for entry in scene.entries],
    }


def clear_previous_outputs(output_dir: Path) -> None:
    """Remove previous generated cleaned files for one session."""

    for scene_file in output_dir.glob(CLEAN_SCENE_PATTERN):
        scene_file.unlink()
    index_file = output_dir / INDEX_FILE_NAME
    if index_file.exists():
        index_file.unlink()


def write_cleaned_scenes(scenes: list[CleanScene], output_dir: Path) -> None:
    """Write one JSON file per cleaned scene."""

    output_dir.mkdir(parents=True, exist_ok=True)
    clear_previous_outputs(output_dir)
    for scene in scenes:
        (output_dir / f"{scene.scene_id}.json").write_text(
            json.dumps(scene_to_payload(scene), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def write_clean_index(session_id: str, scenes: list[CleanScene], output_dir: Path) -> None:
    """Write the clean_index.json summary file."""

    payload = {
        "session_id": session_id,
        "total_scenes": len(scenes),
        "total_entries": total_entries(scenes),
        "type_distribution": entry_type_distribution(scenes),
        "speakers": detected_speakers(scenes),
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "entries": len(scene.entries),
                "type_distribution": entry_type_distribution([scene]),
                "speakers": detected_speakers([scene]),
            }
            for scene in scenes
        ],
    }
    (output_dir / INDEX_FILE_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def clean_session(
    series_name: str,
    session_name: str | None = None,
    *,
    force: bool = False,
) -> CleanResult:
    """Clean and classify one scene-candidate session."""

    project_root = get_project_root()
    series_root = resolve_series_root(project_root, series_name)
    session_dir = resolve_session_dir(series_root, session_name)
    session_id = session_dir.name
    output_dir = series_root / CLEANED_TRANSCRIPTS_DIR / session_id
    metadata_path = series_root / CLEANED_SESSIONS_PATH
    source_sha256 = sha256_scene_session(session_dir)
    registry = load_cleaned_sessions(metadata_path)

    if has_cleaned_sha(registry, source_sha256) and not force:
        print("Cleaned session already processed. Use --force to regenerate.")
        return CleanResult(scenes=[], skipped=True, source_dir=session_dir, output_dir=output_dir)

    LOGGER.info("Series: %s", series_name)
    LOGGER.info("Cleaning scene candidates: %s", session_dir)
    scenes = [clean_scene(scene_file, session_id) for scene_file in list_scene_files(session_dir)]

    LOGGER.info("Writing %s cleaned scenes to: %s", len(scenes), output_dir)
    write_cleaned_scenes(scenes, output_dir)
    write_clean_index(session_id, scenes, output_dir)
    record_cleaned_session(
        registry,
        session_id=session_id,
        source_path=relative_to_series(session_dir, series_root),
        source_sha256=source_sha256,
        output_dir=relative_to_series(output_dir, series_root),
        scenes=scenes,
    )
    write_cleaned_sessions(metadata_path, registry)

    return CleanResult(scenes=scenes, skipped=False, source_dir=session_dir, output_dir=output_dir)


def summarize(scenes: list[CleanScene]) -> str:
    """Build a concise human-readable summary for CLI output."""

    distribution = entry_type_distribution(scenes)
    distribution_text = ", ".join(
        f"{entry_type}={count}" for entry_type, count in distribution.items()
    )
    speakers = detected_speakers(scenes)
    return "\n".join(
        [
            f"Escenas limpiadas: {len(scenes)}",
            f"Entradas clasificadas: {total_entries(scenes)}",
            f"Distribucion por tipos: {distribution_text}",
            f"Speakers detectados: {', '.join(speakers) if speakers else 'ninguno'}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Classify scene candidate transcripts into cleaned JSON entries."
    )
    parser.add_argument(
        "--series",
        required=True,
        help="Series directory name, for example La_Frecuencia_Bauman.",
    )
    parser.add_argument(
        "--session",
        default=None,
        help="Optional scene candidate session name. Defaults to the newest session.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate outputs even if the same input SHA-256 was already cleaned.",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    result = clean_session(args.series, args.session, force=args.force)
    if not result.skipped:
        print(summarize(result.scenes))


if __name__ == "__main__":
    main()
