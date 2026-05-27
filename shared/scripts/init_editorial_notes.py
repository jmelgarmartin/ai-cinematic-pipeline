"""Create editable editorial note templates for screenplay scenes.

This stage bootstraps one markdown notes file per screenplay scene. It is
deterministic, does not use LLMs, and never overwrites existing human notes
unless --force is explicitly passed.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path


LOGGER = logging.getLogger(__name__)

SCREENPLAY_DIR = Path("processing") / "screenplay"
EDITORIAL_NOTES_DIR = Path("editorial_notes")
SCREENPLAY_SCENE_PATTERN = "escena_*.md"
NOTE_TEMPLATE = """# {scene_id}

## Eliminar

## Mantener

## Planos sugeridos

## Intención
"""


@dataclass(frozen=True)
class InitResult:
    """Summary of an editorial-notes bootstrap run."""

    created: int
    skipped: int
    overwritten: int
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


def resolve_screenplay_session(series_root: Path, session_name: str) -> Path:
    """Resolve a screenplay session directory."""

    session_dir = series_root / SCREENPLAY_DIR / session_name
    if not session_dir.is_dir():
        raise FileNotFoundError(f"Screenplay session not found: {session_dir}")
    return session_dir


def list_screenplay_scene_files(session_dir: Path) -> list[Path]:
    """Return screenplay scene markdown files in deterministic order."""

    scene_files = sorted(session_dir.glob(SCREENPLAY_SCENE_PATTERN))
    if not scene_files:
        raise FileNotFoundError(f"No screenplay scene files found in {session_dir}")
    return scene_files


def note_path_for_scene(output_dir: Path, screenplay_file: Path) -> Path:
    """Return the expected notes path for one screenplay scene file."""

    return output_dir / f"{screenplay_file.stem}.notes.md"


def render_note_template(scene_id: str) -> str:
    """Render an empty editorial note template for one scene."""

    return NOTE_TEMPLATE.format(scene_id=scene_id)


def write_note_template(path: Path, scene_id: str) -> None:
    """Write one editorial note template with explicit UTF-8 encoding."""

    path.write_text(render_note_template(scene_id), encoding="utf-8")


def init_editorial_notes(
    series_name: str,
    session_name: str,
    *,
    force: bool = False,
) -> InitResult:
    """Create missing editorial note templates for one screenplay session."""

    project_root = get_project_root()
    series_root = resolve_series_root(project_root, series_name)
    source_dir = resolve_screenplay_session(series_root, session_name)
    output_dir = series_root / EDITORIAL_NOTES_DIR / session_name
    scene_files = list_screenplay_scene_files(source_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0
    overwritten = 0

    LOGGER.info("Series: %s", series_name)
    LOGGER.info("Initializing editorial notes from: %s", source_dir)
    for screenplay_file in scene_files:
        note_path = note_path_for_scene(output_dir, screenplay_file)
        if note_path.exists() and not force:
            skipped += 1
            continue
        if note_path.exists() and force:
            overwritten += 1
        else:
            created += 1
        write_note_template(note_path, screenplay_file.stem)

    return InitResult(
        created=created,
        skipped=skipped,
        overwritten=overwritten,
        source_dir=source_dir,
        output_dir=output_dir,
    )


def summarize(result: InitResult) -> str:
    """Build a concise human-readable summary for CLI output."""

    return "\n".join(
        [
            f"Escenas creadas: {result.created}",
            f"Escenas omitidas: {result.skipped}",
            f"Escenas sobrescritas: {result.overwritten}",
            f"Notas en: {result.output_dir}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Create editable editorial note templates for screenplay scenes."
    )
    parser.add_argument(
        "--series",
        required=True,
        help="Series directory name, for example La_Frecuencia_Bauman.",
    )
    parser.add_argument(
        "--session",
        required=True,
        help="Screenplay session name to initialize notes for.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing note templates for the requested session.",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    print(summarize(init_editorial_notes(args.series, args.session, force=args.force)))


if __name__ == "__main__":
    main()
