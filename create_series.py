import argparse
from pathlib import Path


PRIVATE_GITIGNORE_TEMPLATE = """# Series private data: {series_name}
{series_name}/input/raw_sessions/
{series_name}/processing/scene_candidates/
{series_name}/processing/cleaned_transcripts/
{series_name}/processing/screenplay/
{series_name}/processing/storyboard/
{series_name}/processing/prompts/
{series_name}/processing/metadata/
"""

SERIES_SCRIPTS_README = """# Scripts especificos de la serie

Esta carpeta queda reservada para overrides, utilidades puntuales o scripts que solo tengan sentido para esta serie.

Las herramientas reutilizables del pipeline viven en `shared/scripts/`.
"""


def build_private_gitignore_section(series_name: str) -> str:
    """Build the per-series private data ignore section."""

    return PRIVATE_GITIGNORE_TEMPLATE.format(series_name=series_name).strip()


def ensure_gitignore_section(project_root: Path, series_name: str) -> None:
    """Append per-series privacy ignores without duplicating existing entries."""

    gitignore_path = project_root / ".gitignore"
    section = build_private_gitignore_section(series_name)
    existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""

    if f"# Series private data: {series_name}" in existing:
        return

    separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
    gitignore_path.write_text(f"{existing}{separator}{section}\n", encoding="utf-8")


def ensure_file(path: Path, content: str | None = None) -> None:
    """Create a file and optionally seed it when it is empty."""

    path.touch(exist_ok=True)
    if content is not None and path.stat().st_size == 0:
        path.write_text(content, encoding="utf-8")


def create_series_structure(series_name: str) -> None:
    """Create a new series folder structure and protect private data in git."""

    root = Path(__file__).resolve().parent
    series_root = root / series_name

    directories = [
        # Shared already exists outside this script

        # INPUT
        series_root / "input" / "raw_sessions",
        series_root / "input" / "transcripts",
        series_root / "input" / "audio",
        series_root / "input" / "references",

        # PROCESSING
        series_root / "processing" / "scene_candidates",
        series_root / "processing" / "cleaned_transcripts",
        series_root / "processing" / "screenplay",
        series_root / "processing" / "storyboard",
        series_root / "processing" / "prompts",
        series_root / "processing" / "metadata",

        # ASSETS
        series_root / "assets" / "characters",
        series_root / "assets" / "locations",
        series_root / "assets" / "props",
        series_root / "assets" / "style",

        # VIDEO
        series_root / "video" / "scenes",
        series_root / "video" / "clips",
        series_root / "video" / "renders",
        series_root / "video" / "final",

        # AUDIO
        series_root / "audio" / "voices",
        series_root / "audio" / "music",
        series_root / "audio" / "ambience",
        series_root / "audio" / "final_mix",

        # OTHER
        series_root / "scripts",
        series_root / "config",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Created: {directory}")

    # Base files. Pipeline tools live in shared/scripts; the per-series scripts
    # folder is reserved for optional overrides or one-off utilities.
    base_files: dict[Path, str | None] = {
        series_root / "README.md": None,
        series_root / "config" / "series_config.yaml": None,
        series_root / "scripts" / "README.md": SERIES_SCRIPTS_README,
    }

    for file, content in base_files.items():
        ensure_file(file, content)
        print(f"[FILE] Created: {file}")

    ensure_gitignore_section(root, series_name)
    print(f"[OK] Privacy ignores ensured for: {series_name}")

    print("\nSeries structure created successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create folder structure for an AI series project."
    )

    parser.add_argument(
        "series_name",
        type=str,
        help="Name of the series."
    )

    args = parser.parse_args()

    create_series_structure(args.series_name)
