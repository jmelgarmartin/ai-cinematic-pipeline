"""Streamlit UI for iterative local LLM scene editing."""

from __future__ import annotations

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
from shared.scene_editor.generation_manager import (  # noqa: E402
    generate_initial_draft,
    refine_draft,
)
from shared.scene_editor.models import GenerationSettings  # noqa: E402
from shared.scene_editor.ollama_client import OllamaClient, OllamaError  # noqa: E402
from shared.scene_editor.storage import (  # noqa: E402
    final_paths,
    latest_draft,
    list_draft_numbers,
    list_scene_ids,
    list_series,
    list_sessions,
    load_draft,
    load_scene_source,
    save_final,
    series_root,
)


def reset_scene_index_when_context_changes(series: str, session: str) -> None:
    """Reset active scene when the selected series/session changes."""

    context = f"{series}/{session}"
    if st.session_state.get("scene_editor_context") != context:
        st.session_state["scene_editor_context"] = context
        st.session_state["scene_editor_index"] = 0


def set_scene_index(index: int) -> None:
    """Set active scene index."""

    st.session_state["scene_editor_index"] = index


def select_active_draft(root: Path, session_id: str, scene_id: str):
    """Return the draft selected in the UI, defaulting to latest."""

    draft_numbers = list_draft_numbers(root, session_id, scene_id)
    if not draft_numbers:
        return None
    labels = [f"draft_{number:03d}" for number in draft_numbers]
    selected_label = st.selectbox("Historial de drafts", labels, index=len(labels) - 1)
    selected_number = int(selected_label.split("_")[1])
    return load_draft(root, session_id, scene_id, selected_number)


def main() -> None:
    """Render the scene editor UI."""

    st.set_page_config(page_title="SeriesIA Scene Editor", layout="wide")
    st.title("SeriesIA Scene Editor")

    series_names = list_series()
    if not series_names:
        st.error("No series directories found.")
        return

    top_series, top_session, top_scene, top_counter = st.columns([1.2, 1.7, 1.4, 0.8])
    with top_series:
        selected_series = st.selectbox("Serie", series_names)

    root = series_root(selected_series)
    sessions = list_sessions(root)
    if not sessions:
        st.warning("No screenplay sessions found for this series.")
        return

    with top_session:
        selected_session = st.selectbox("Sesión", sessions)

    reset_scene_index_when_context_changes(selected_series, selected_session)
    scene_ids = list_scene_ids(root, selected_session)
    if not scene_ids:
        st.warning("No scenes found for this session.")
        return

    current_index = min(st.session_state.get("scene_editor_index", 0), len(scene_ids) - 1)
    with top_scene:
        selected_scene = st.selectbox("Escena", scene_ids, index=current_index)
    selected_index = scene_ids.index(selected_scene)
    st.session_state["scene_editor_index"] = selected_index

    with top_counter:
        st.metric("Escena", f"{selected_index + 1} / {len(scene_ids)}")

    try:
        source = load_scene_source(root, selected_series, selected_session, selected_scene)
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    settings_col_a, settings_col_b, settings_col_c = st.columns([1.4, 1, 1])
    with settings_col_a:
        model = st.text_input("Modelo Ollama", value=DEFAULT_MODEL)
    with settings_col_b:
        temperature = st.slider("Temperatura", 0.0, 1.2, DEFAULT_TEMPERATURE, 0.05)
    with settings_col_c:
        st.metric("Max tokens", DEFAULT_MAX_TOKENS)
        timeout_seconds = st.number_input(
            "Timeout (s)",
            min_value=30,
            max_value=3600,
            value=DEFAULT_TIMEOUT_SECONDS,
            step=30,
        )
    settings = GenerationSettings(
        model=model.strip() or DEFAULT_MODEL,
        temperature=float(temperature),
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    ollama_client = OllamaClient(timeout_seconds=int(timeout_seconds))

    base_col, notes_col, draft_col = st.columns(3)
    with base_col:
        st.subheader("Screenplay base")
        st.text_area(
            "Screenplay base",
            source.screenplay_markdown,
            height=520,
            disabled=True,
            label_visibility="collapsed",
        )
    with notes_col:
        st.subheader("Notas editoriales")
        st.text_area(
            "Notas editoriales",
            source.editorial_notes_markdown or "_Sin notas editoriales._",
            height=520,
            disabled=True,
            label_visibility="collapsed",
        )
    with draft_col:
        st.subheader("Draft cinematográfico")
        selected_draft = select_active_draft(root, selected_session, selected_scene)
        draft_text = selected_draft.response if selected_draft else ""
        if selected_draft:
            st.caption(
                f"Draft activo: {selected_draft.draft_number:03d} | "
                f"Prompt: {selected_draft.prompt_version}"
            )
            st.markdown(draft_text)
            with st.expander("Texto raw del draft", expanded=False):
                st.text_area(
                    "Texto raw del draft",
                    draft_text,
                    height=520,
                    disabled=True,
                    label_visibility="collapsed",
                )
            if selected_draft.cleaned_response:
                st.info(f"Salida limpiada: {selected_draft.cleanup_reason}")
        else:
            st.info("Aun no hay draft para esta escena.")

    feedback = st.text_area(
        "Ajuste del director para el siguiente draft",
        height=120,
        placeholder="Ej: hazla mas visual, reduce exposicion, conserva la radio...",
    )

    prev_col, generate_col, refine_col, final_col, next_col = st.columns(
        [1, 1.35, 1.6, 1.2, 1]
    )
    with prev_col:
        if st.button("Anterior", disabled=selected_index == 0, use_container_width=True):
            set_scene_index(selected_index - 1)
            st.rerun()
    with generate_col:
        if st.button("Generar primer draft", type="primary", use_container_width=True):
            with st.spinner("Generando borrador con Ollama..."):
                try:
                    record = generate_initial_draft(
                        series_root=root,
                        source=source,
                        settings=settings,
                        client=ollama_client,
                    )
                    st.success(f"Draft {record.draft_number:03d} generado.")
                    st.rerun()
                except OllamaError as exc:
                    st.error(str(exc))
                except Exception as exc:  # pragma: no cover - UI guardrail
                    st.error(f"Error inesperado generando draft: {exc}")
    with refine_col:
        if st.button(
            "Generar nuevo draft con ajuste",
            disabled=selected_draft is None,
            use_container_width=True,
        ):
            if not feedback.strip():
                st.warning("Escribe un ajuste del director antes de continuar.")
            else:
                with st.spinner("Generando nueva version con Ollama..."):
                    try:
                        record = refine_draft(
                            series_root=root,
                            source=source,
                            previous_draft=selected_draft.response if selected_draft else "",
                            user_feedback=feedback,
                            settings=settings,
                            client=ollama_client,
                        )
                        st.success(f"Draft {record.draft_number:03d} refinado.")
                        st.rerun()
                    except OllamaError as exc:
                        st.error(str(exc))
                    except Exception as exc:  # pragma: no cover - UI guardrail
                        st.error(f"Error inesperado refinando draft: {exc}")
    with final_col:
        if st.button("Guardar final", disabled=selected_draft is None, use_container_width=True):
            if selected_draft:
                save_final(root, selected_session, selected_draft)
                final_md, _final_json = final_paths(root, selected_session, selected_scene)
                st.success(f"Final guardado: {final_md.name}")
    with next_col:
        if st.button(
            "Siguiente",
            disabled=selected_index == len(scene_ids) - 1,
            use_container_width=True,
        ):
            set_scene_index(selected_index + 1)
            st.rerun()

    final_md, final_json = final_paths(root, selected_session, selected_scene)
    with st.expander("Final aceptado", expanded=False):
        if final_md.exists():
            st.markdown(final_md.read_text(encoding="utf-8"))
            st.caption(f"Metadata: {final_json}")
        else:
            st.info("Todavia no hay version final aceptada para esta escena.")


if __name__ == "__main__":
    main()
