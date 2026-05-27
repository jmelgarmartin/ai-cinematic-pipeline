"""Local Streamlit UI for reviewing screenplay scenes and editorial notes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.scripts.apply_editorial_notes import apply_editorial_notes  # noqa: E402


SCREENPLAY_DIR = Path("processing") / "screenplay"
EDITORIAL_NOTES_DIR = Path("editorial_notes")
ANNOTATED_SCREENPLAY_DIR = Path("processing") / "annotated_screenplay"
SCREENPLAY_SCENE_PATTERN = "escena_*.md"
NOTE_TEMPLATE = """# {scene_id}

## Eliminar

## Mantener

## Planos sugeridos

## Intención
"""


def list_series(project_root: Path) -> list[str]:
    """Return local series directories that are plausible pipeline targets."""

    excluded = {".git", ".venv", "__pycache__", "docs", "shared"}
    return sorted(
        path.name
        for path in project_root.iterdir()
        if path.is_dir() and path.name not in excluded and not path.name.startswith(".")
    )


def list_sessions(series_root: Path) -> list[str]:
    """Return screenplay sessions for a series."""

    screenplay_root = series_root / SCREENPLAY_DIR
    if not screenplay_root.is_dir():
        return []
    return sorted(
        path.name
        for path in screenplay_root.iterdir()
        if path.is_dir() and any(path.glob(SCREENPLAY_SCENE_PATTERN))
    )


def list_scene_files(session_dir: Path) -> list[Path]:
    """Return screenplay scene files, ignoring screenplay_index.json."""

    return sorted(session_dir.glob(SCREENPLAY_SCENE_PATTERN))


def notes_path(series_root: Path, session: str, scene_id: str) -> Path:
    """Return the editable notes path for a scene."""

    return series_root / EDITORIAL_NOTES_DIR / session / f"{scene_id}.notes.md"


def annotated_path(series_root: Path, session: str, scene_id: str) -> Path:
    """Return the annotated JSON path for a scene."""

    return (
        series_root
        / ANNOTATED_SCREENPLAY_DIR
        / session
        / f"{scene_id}.annotated.json"
    )


def ensure_notes_file(path: Path, scene_id: str) -> None:
    """Create an empty notes template when none exists."""

    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(NOTE_TEMPLATE.format(scene_id=scene_id), encoding="utf-8")


def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""

    return path.read_text(encoding="utf-8")


def write_notes(path: Path, content: str) -> None:
    """Write editorial notes with UTF-8 encoding."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def load_annotated_payload(path: Path) -> dict[str, Any] | None:
    """Load annotated JSON if it exists."""

    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def reset_scene_index_when_context_changes(series: str, session: str) -> None:
    """Keep navigation stable when the selected series or session changes."""

    context = f"{series}/{session}"
    if st.session_state.get("editorial_context") != context:
        st.session_state["editorial_context"] = context
        st.session_state["scene_index"] = 0


def set_scene_index(index: int) -> None:
    """Set the active scene index."""

    st.session_state["scene_index"] = index


def main() -> None:
    """Render the local editorial review app."""

    st.set_page_config(page_title="SeriesIA Editorial", layout="wide")
    st.title("SeriesIA Editorial")

    series_names = list_series(PROJECT_ROOT)
    if not series_names:
        st.error("No series directories found.")
        return

    top_series, top_session, top_scene, top_counter = st.columns([1.2, 1.7, 1.4, 0.8])
    with top_series:
        selected_series = st.selectbox("Serie", series_names)

    series_root = PROJECT_ROOT / selected_series
    sessions = list_sessions(series_root)
    if not sessions:
        st.warning("No screenplay sessions found for this series.")
        return

    with top_session:
        selected_session = st.selectbox("Sesión", sessions)

    reset_scene_index_when_context_changes(selected_series, selected_session)
    session_dir = series_root / SCREENPLAY_DIR / selected_session
    scene_files = list_scene_files(session_dir)
    if not scene_files:
        st.warning("No screenplay scene files found for this session.")
        return

    scene_ids = [path.stem for path in scene_files]
    current_index = min(st.session_state.get("scene_index", 0), len(scene_ids) - 1)
    with top_scene:
        selected_scene = st.selectbox(
            "Escena",
            scene_ids,
            index=current_index,
            key="scene_select",
        )
    selected_index = scene_ids.index(selected_scene)
    st.session_state["scene_index"] = selected_index

    with top_counter:
        st.metric("Escena", f"{selected_index + 1} / {len(scene_ids)}")

    screenplay_file = scene_files[selected_index]
    note_file = notes_path(series_root, selected_session, selected_scene)
    ensure_notes_file(note_file, selected_scene)

    screenplay_markdown = read_text(screenplay_file)
    notes_markdown = read_text(note_file)

    left, right = st.columns(2)
    with left:
        st.subheader("Screenplay base")
        st.text_area(
            "Screenplay base",
            screenplay_markdown,
            height=620,
            disabled=True,
            label_visibility="collapsed",
        )

    notes_key = f"notes::{selected_series}::{selected_session}::{selected_scene}"
    with right:
        st.subheader("Notas editoriales")
        edited_notes = st.text_area(
            "Notas editoriales",
            notes_markdown,
            height=620,
            key=notes_key,
            label_visibility="collapsed",
        )

    nav_prev, nav_save, nav_next, nav_apply = st.columns([1, 1.2, 1, 1.2])
    with nav_prev:
        if st.button("Anterior", disabled=selected_index == 0, use_container_width=True):
            set_scene_index(selected_index - 1)
            st.rerun()
    with nav_save:
        if st.button("Guardar notas", type="primary", use_container_width=True):
            write_notes(note_file, edited_notes)
            st.success(f"Notas guardadas: {note_file.name}")
    with nav_next:
        if st.button(
            "Siguiente",
            disabled=selected_index == len(scene_ids) - 1,
            use_container_width=True,
        ):
            set_scene_index(selected_index + 1)
            st.rerun()
    with nav_apply:
        if st.button("Aplicar notas", use_container_width=True):
            try:
                write_notes(note_file, edited_notes)
                result = apply_editorial_notes(
                    selected_series,
                    selected_session,
                    force=True,
                )
                st.success(f"Notas aplicadas a {len(result.scenes)} escenas.")
            except Exception as exc:  # pragma: no cover - UI guardrail
                st.error(f"No se pudieron aplicar las notas: {exc}")

    current_annotated_path = annotated_path(series_root, selected_session, selected_scene)
    with st.expander("Annotated screenplay", expanded=False):
        payload = load_annotated_payload(current_annotated_path)
        if payload is None:
            st.info("Todavía no existe annotated_screenplay para esta escena.")
        else:
            st.json(payload)


if __name__ == "__main__":
    main()
