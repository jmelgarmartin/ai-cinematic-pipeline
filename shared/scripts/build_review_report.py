"""Build a manual review report for unclear cleaned transcript entries.

This tool is deterministic and does not change classifications. It only reads
cleaned transcript JSON files and writes a private report for rule refinement.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import DefaultDict


LOGGER = logging.getLogger(__name__)

CLEANED_TRANSCRIPTS_DIR = Path("processing") / "cleaned_transcripts"
REVIEW_REPORTS_DIR = Path("processing") / "review_reports"
CLEAN_SCENE_PATTERN = "escena_*.json"
REPORT_FILE_NAME = "unclear_entries.md"
INDEX_FILE_NAME = "review_index.json"
UNCLEAR_TYPE = "unclear"
TOP_PREFIX_LIMIT = 12


@dataclass(frozen=True)
class CleanEntry:
    """One cleaned transcript entry."""

    entry_id: int
    line_number: int
    speaker: str | None
    type: str
    text: str
    raw_line: str


@dataclass(frozen=True)
class CleanScene:
    """One cleaned scene with entries."""

    scene_id: str
    session_id: str
    entries: list[CleanEntry]


@dataclass(frozen=True)
class ReviewReport:
    """Collected unclear entries and aggregate summary."""

    session_id: str
    scenes: list[CleanScene]
    unclear_by_scene: dict[str, list[CleanEntry]]


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
        )
        for entry in payload["entries"]
    ]
    return CleanScene(
        scene_id=str(payload["scene_id"]),
        session_id=str(payload["session_id"]),
        entries=entries,
    )


def collect_unclear_entries(scenes: list[CleanScene]) -> dict[str, list[CleanEntry]]:
    """Group unclear entries by scene id."""

    grouped: DefaultDict[str, list[CleanEntry]] = defaultdict(list)
    for scene in scenes:
        for entry in scene.entries:
            if entry.type == UNCLEAR_TYPE:
                grouped[scene.scene_id].append(entry)
    return dict(sorted(grouped.items()))


def speaker_label(speaker: str | None) -> str:
    """Return a printable speaker label."""

    return speaker or "UNKNOWN_SPEAKER"


def affected_speakers(report: ReviewReport) -> list[str]:
    """Return sorted speakers with unclear entries."""

    speakers = {
        speaker_label(entry.speaker)
        for entries in report.unclear_by_scene.values()
        for entry in entries
    }
    return sorted(speakers)


def total_unclear(report: ReviewReport) -> int:
    """Return total unclear entry count."""

    return sum(len(entries) for entries in report.unclear_by_scene.values())


def normalize_prefix_text(text: str) -> str:
    """Normalize an initial phrase for coarse pattern spotting."""

    words = re.findall(r"[\wÁÉÍÓÚÜÑáéíóúüñ]+", text.lower())
    if not words:
        return "(empty)"
    return " ".join(words[:4])


def top_initial_phrases(report: ReviewReport) -> list[tuple[str, int]]:
    """Return frequent initial phrases among unclear entries."""

    counts = Counter(
        normalize_prefix_text(entry.text)
        for entries in report.unclear_by_scene.values()
        for entry in entries
    )
    return counts.most_common(TOP_PREFIX_LIMIT)


def build_report(session_dir: Path) -> ReviewReport:
    """Load cleaned scenes and collect unclear entries."""

    scenes = [load_clean_scene(path) for path in list_clean_scene_files(session_dir)]
    session_id = session_dir.name
    return ReviewReport(
        session_id=session_id,
        scenes=scenes,
        unclear_by_scene=collect_unclear_entries(scenes),
    )


def render_markdown(report: ReviewReport) -> str:
    """Render the unclear review markdown report."""

    lines = [
        "# UNCLEAR ENTRIES REVIEW",
        "",
        "## SUMMARY",
        "",
        f"- Session: {report.session_id}",
        f"- Total unclear: {total_unclear(report)}",
        f"- Total scenes with unclear: {len(report.unclear_by_scene)}",
        f"- Speakers affected: {', '.join(affected_speakers(report)) or 'none'}",
        "",
        "### Top initial phrases",
        "",
    ]

    for phrase, count in top_initial_phrases(report):
        lines.append(f"- `{phrase}`: {count}")

    for scene_id, entries in report.unclear_by_scene.items():
        lines.extend(["", f"## {scene_id.replace('_', ' ').upper()}", ""])
        for entry in entries:
            lines.extend(
                [
                    f"### Entry {entry.entry_id}",
                    f"- Speaker: {speaker_label(entry.speaker)}",
                    f"- Line: {entry.line_number}",
                    f"- Text: {entry.text}",
                    f"- Raw line: {entry.raw_line}",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def write_review_index(report: ReviewReport, output_dir: Path) -> None:
    """Write review_index.json."""

    payload = {
        "session_id": report.session_id,
        "total_unclear": total_unclear(report),
        "scenes_with_unclear": len(report.unclear_by_scene),
        "speakers": affected_speakers(report),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "top_initial_phrases": [
            {"phrase": phrase, "count": count}
            for phrase, count in top_initial_phrases(report)
        ],
    }
    (output_dir / INDEX_FILE_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_report(report: ReviewReport, output_dir: Path) -> None:
    """Write markdown report and JSON index."""

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / REPORT_FILE_NAME).write_text(render_markdown(report), encoding="utf-8")
    write_review_index(report, output_dir)


def build_review_report(series_name: str, session_name: str | None = None) -> ReviewReport:
    """Build and write an unclear entries review report."""

    project_root = get_project_root()
    series_root = resolve_series_root(project_root, series_name)
    session_dir = resolve_session_dir(series_root, session_name)
    output_dir = series_root / REVIEW_REPORTS_DIR / session_dir.name

    LOGGER.info("Series: %s", series_name)
    LOGGER.info("Building unclear review report from: %s", session_dir)
    report = build_report(session_dir)
    LOGGER.info("Writing review report to: %s", output_dir)
    write_report(report, output_dir)
    return report


def summarize(report: ReviewReport) -> str:
    """Build a concise human-readable summary for CLI output."""

    return "\n".join(
        [
            f"Session: {report.session_id}",
            f"Unclear entries: {total_unclear(report)}",
            f"Scenes with unclear: {len(report.unclear_by_scene)}",
            f"Speakers affected: {', '.join(affected_speakers(report)) or 'none'}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Build a manual review report for unclear cleaned entries."
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
    return parser


def main() -> None:
    """CLI entrypoint."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    report = build_review_report(args.series, args.session)
    print(summarize(report))


if __name__ == "__main__":
    main()
