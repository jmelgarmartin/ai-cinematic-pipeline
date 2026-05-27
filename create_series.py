from pathlib import Path
import argparse


def create_series_structure(series_name: str) -> None:
    """
    Create the folder structure for a new AI series project.
    """

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

    # Base files
    base_files = [
        series_root / "README.md",
        series_root / "config" / "series_config.yaml",

        series_root / "scripts" / "00_split_full_session.py",
        series_root / "scripts" / "01_clean_transcript.py",
        series_root / "scripts" / "02_extract_scenes.py",
        series_root / "scripts" / "03_build_screenplay.py",
        series_root / "scripts" / "04_generate_storyboard.py",
        series_root / "scripts" / "05_generate_prompts.py",
        series_root / "scripts" / "06_build_episode.py",
    ]

    for file in base_files:
        file.touch(exist_ok=True)
        print(f"[FILE] Created: {file}")

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