"""Streamlit UI for storyboard breakdown generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.scene_editor.config import (  # noqa: E402
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
)
from shared.scene_editor.ollama_client import OllamaClient, OllamaError  # noqa: E402
from shared.storyboard.models import StoryboardSettings  # noqa: E402
from shared.storyboard.storage import (  # noqa: E402
    list_scene_ids,
    list_series,
    list_sessions,
    load_storyboard_source,
    read_storyboard_json,
    read_storyboard_markdown,
    save_storyboard,
    series_root,
    storyboard_paths,
)
from shared.storyboard.storyboard_generator import generate_storyboard  # noqa: E402


MODEL_OPTIONS = ("gemma4:latest", "qwen3:30b", "custom")


def reset_scene_index_when_context_changes(series: str, session: str) -> None:
    """Reset active scene when series/session changes."""

    context = f"{series}/{session}"
    if st.session_state.get("storyboard_context") != context:
        st.session_state["storyboard_context"] = context
        st.session_state["storyboard_scene_index"] = 0
        st.session_state["storyboard_shot_index"] = 0


def set_shot_index(index: int) -> None:
    """Set active shot index."""

    st.session_state["storyboard_shot_index"] = index


def render_shot_browser(storyboard_json: dict[str, object]) -> None:
    """Render shot navigation and details."""

    shots = storyboard_json.get("shots", [])
    if not isinstance(shots, list) or not shots:
        st.info("Todavia no hay shots en el storyboard.")
        return

    current_index = min(st.session_state.get("storyboard_shot_index", 0), len(shots) - 1)
    labels = [f"SHOT {int(shot.get('shot_id', index + 1)):03d}" for index, shot in enumerate(shots)]
    selected_label = st.selectbox("Shot", labels, index=current_index)
    selected_index = labels.index(selected_label)
    st.session_state["storyboard_shot_index"] = selected_index
    shot = shots[selected_index]
    if not isinstance(shot, dict):
        st.error("Shot invalido.")
        return

    prev_col, metric_col, next_col = st.columns([1, 2, 1])
    with prev_col:
        if st.button("Shot anterior", disabled=selected_index == 0, use_container_width=True):
            set_shot_index(selected_index - 1)
            st.rerun()
    with metric_col:
        st.metric("Shot", f"{selected_index + 1} / {len(shots)}")
    with next_col:
        if st.button(
            "Shot siguiente",
            disabled=selected_index == len(shots) - 1,
            use_container_width=True,
        ):
            set_shot_index(selected_index + 1)
            st.rerun()

    st.markdown(f"### SHOT {int(shot.get('shot_id', selected_index + 1)):03d}")
    meta_a, meta_b, meta_c = st.columns(3)
    with meta_a:
        st.caption(f"Type: {shot.get('shot_type', '')}")
        st.caption(f"Camera: {shot.get('camera_motion', '')}")
    with meta_b:
        st.caption(f"Location: {shot.get('location', '')}")
        st.caption(f"Time: {shot.get('time_of_day', '')}")
    with meta_c:
        st.caption(f"Mood: {shot.get('mood', '')}")
        st.caption(f"Lighting: {shot.get('lighting', '')}")
    st.write(shot.get("description", ""))
    elements = shot.get("visual_elements", [])
    if isinstance(elements, list) and elements:
        st.markdown("Visual elements:")
        for element in elements:
            st.markdown(f"- {element}")


def main() -> None:
    """Render storyboard breakdown UI."""

    st.set_page_config(page_title="SeriesIA Storyboard", layout="wide")
    st.title("SeriesIA Storyboard")

    series_names = list_series()
    if not series_names:
        st.error("No series directories found.")
        return

    top_series, top_session, top_scene = st.columns([1.1, 1.6, 1.2])
    with top_series:
        selected_series = st.selectbox("Serie", series_names)

    root = series_root(selected_series)
    sessions = list_sessions(root)
    if not sessions:
        st.warning("No final screenplay sessions found for this series.")
        return

    with top_session:
        selected_session = st.selectbox("Sesion", sessions)

    reset_scene_index_when_context_changes(selected_series, selected_session)
    scene_ids = list_scene_ids(root, selected_session)
    if not scene_ids:
        st.warning("No final screenplay scenes found for this session.")
        return

    current_scene_index = min(
        st.session_state.get("storyboard_scene_index", 0),
        len(scene_ids) - 1,
    )
    with top_scene:
        selected_scene = st.selectbox("Escena", scene_ids, index=current_scene_index)
    st.session_state["storyboard_scene_index"] = scene_ids.index(selected_scene)

    source = load_storyboard_source(root, selected_series, selected_session, selected_scene)

    settings_a, settings_b, settings_c, settings_d = st.columns([1.1, 1.4, 1, 1])
    with settings_a:
        model_choice = st.selectbox("Modelo", MODEL_OPTIONS, key="storyboard_model_choice")
    with settings_b:
        custom_model = st.text_input(
            "Modelo custom",
            value=st.session_state.get("storyboard_custom_model", DEFAULT_MODEL),
            key="storyboard_custom_model",
            disabled=model_choice != "custom",
        )
    with settings_c:
        temperature = st.slider(
            "Temperatura",
            0.0,
            1.2,
            DEFAULT_TEMPERATURE,
            0.05,
            key="storyboard_temperature",
        )
    with settings_d:
        max_tokens = st.number_input(
            "Max tokens",
            min_value=512,
            max_value=32000,
            value=DEFAULT_MAX_TOKENS,
            step=512,
            key="storyboard_max_tokens",
        )
        timeout_seconds = st.number_input(
            "Timeout (s)",
            min_value=30,
            max_value=3600,
            value=DEFAULT_TIMEOUT_SECONDS,
            step=30,
            key="storyboard_timeout_seconds",
        )

    model = custom_model if model_choice == "custom" else model_choice
    settings = StoryboardSettings(
        model=model.strip() or DEFAULT_MODEL,
        temperature=float(temperature),
        max_tokens=int(max_tokens),
    )
    client = OllamaClient(timeout_seconds=int(timeout_seconds))

    storyboard_json = read_storyboard_json(root, selected_session, selected_scene)
    storyboard_markdown = read_storyboard_markdown(root, selected_session, selected_scene)
    json_path, md_path = storyboard_paths(root, selected_session, selected_scene)

    action_a, action_b, action_c = st.columns([1.2, 1.2, 3])
    with action_a:
        generate_label = "Regenerar storyboard" if storyboard_json else "Generar storyboard"
        if st.button(generate_label, type="primary", use_container_width=True):
            with st.spinner("Generando storyboard con Ollama..."):
                try:
                    record = generate_storyboard(
                        source=source,
                        settings=settings,
                        client=client,
                    )
                    save_storyboard(root, selected_session, record)
                    st.session_state["storyboard_shot_index"] = 0
                    st.success(f"Storyboard guardado: {json_path.name}")
                    st.rerun()
                except (OllamaError, ValueError, json.JSONDecodeError) as exc:
                    st.error(str(exc))
                except Exception as exc:  # pragma: no cover - UI guardrail
                    st.error(f"Error inesperado generando storyboard: {exc}")
    with action_b:
        st.caption(f"JSON: {json_path.name}")
        st.caption(f"Markdown: {md_path.name}")
    with action_c:
        if storyboard_json:
            metadata = storyboard_json.get("metadata", {})
            if isinstance(metadata, dict):
                st.caption(
                    f"Modelo: {metadata.get('model', '')} | "
                    f"Prompt: {metadata.get('prompt_version', '')} | "
                    f"Generado: {metadata.get('timestamp', '')}"
                )

    source_col, storyboard_col = st.columns(2)
    with source_col:
        st.subheader("Final screenplay")
        st.markdown(source.final_screenplay_markdown)
        with st.expander("Texto raw final screenplay", expanded=False):
            st.text_area(
                "Texto raw final screenplay",
                source.final_screenplay_markdown,
                height=520,
                disabled=True,
                label_visibility="collapsed",
            )

    with storyboard_col:
        st.subheader("Storyboard shots")
        if storyboard_json:
            render_shot_browser(storyboard_json)
        else:
            st.info("Todavia no hay storyboard para esta escena.")

    with st.expander("Storyboard markdown", expanded=False):
        if storyboard_markdown:
            st.markdown(storyboard_markdown)
        else:
            st.info("Todavia no hay markdown de storyboard.")

    with st.expander("Storyboard JSON", expanded=False):
        if storyboard_json:
            st.json(storyboard_json)
        else:
            st.info("Todavia no hay JSON de storyboard.")


if __name__ == "__main__":
    main()
