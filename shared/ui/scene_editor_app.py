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
    list_draft_numbers,
    list_scene_ids,
    list_series,
    list_sessions,
    load_draft,
    load_scene_source,
    save_draft_evaluation,
    save_final,
    series_root,
)


MODEL_OPTIONS = ("gemma4:latest", "qwen3:30b", "custom")
EVALUATION_LABELS = {
    "better": "Mejor",
    "same": "Igual",
    "worse": "Peor",
}


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
    """Return available draft numbers and the draft selected in the UI."""

    draft_numbers = list_draft_numbers(root, session_id, scene_id)
    if not draft_numbers:
        return draft_numbers, None
    labels = [f"draft_{number:03d}" for number in draft_numbers]
    selected_label = st.selectbox(
        "Historial de drafts",
        labels,
        index=len(labels) - 1,
        key=f"draft_selector_{session_id}_{scene_id}",
    )
    selected_number = int(selected_label.split("_")[1])
    return draft_numbers, load_draft(root, session_id, scene_id, selected_number)


def previous_draft_for_active(root: Path, session_id: str, scene_id: str, draft_numbers, active):
    """Return the closest draft before the active one, if any."""

    if active is None:
        return None
    previous_numbers = [number for number in draft_numbers if number < active.draft_number]
    if not previous_numbers:
        return None
    return load_draft(root, session_id, scene_id, previous_numbers[-1])


def draft_metadata_text(draft) -> str:
    """Return compact draft metadata for captions."""

    if draft is None:
        return ""
    evaluation = EVALUATION_LABELS.get(draft.user_evaluation, "Sin evaluar")
    source = f" | origen: {draft.source_draft_number:03d}" if draft.source_draft_number else ""
    return (
        f"draft_{draft.draft_number:03d}{source} | {draft.model} | "
        f"temp {draft.temperature:g} | {draft.timestamp} | "
        f"{draft.prompt_version} | {evaluation}"
    )


def render_markdown_with_raw(title: str, markdown: str, *, height: int = 420) -> None:
    """Render markdown and provide raw text in an expander."""

    st.markdown(markdown or "_Sin contenido._")
    with st.expander(f"Texto raw: {title}", expanded=False):
        st.text_area(
            f"Texto raw {title}",
            markdown,
            height=height,
            disabled=True,
            label_visibility="collapsed",
        )


def render_draft_panel(title: str, draft, *, active: bool = False) -> None:
    """Render one draft comparison panel."""

    with st.container(border=True):
        if active:
            st.success(f"{title} activo")
        else:
            st.caption(title)
        if draft is None:
            st.info("No hay draft anterior para comparar.")
            return
        st.caption(draft_metadata_text(draft))
        st.markdown(draft.response)
        with st.expander(f"Texto raw: draft_{draft.draft_number:03d}", expanded=False):
            st.text_area(
                f"Texto raw draft_{draft.draft_number:03d}",
                draft.response,
                height=360,
                disabled=True,
                label_visibility="collapsed",
            )
        if draft.cleaned_response:
            st.info(f"Salida limpiada: {draft.cleanup_reason}")


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

    settings_col_a, settings_col_b, settings_col_c, settings_col_d = st.columns(
        [1.1, 1.4, 1, 1]
    )
    with settings_col_a:
        model_choice = st.selectbox(
            "Modelo",
            MODEL_OPTIONS,
            index=0,
            key="scene_editor_model_choice",
        )
    with settings_col_b:
        custom_model = st.text_input(
            "Modelo custom",
            value=st.session_state.get("scene_editor_custom_model", DEFAULT_MODEL),
            key="scene_editor_custom_model",
            disabled=model_choice != "custom",
        )
    with settings_col_c:
        temperature = st.slider(
            "Temperatura",
            0.0,
            1.2,
            DEFAULT_TEMPERATURE,
            0.05,
            key="scene_editor_temperature",
        )
    with settings_col_d:
        max_tokens = st.number_input(
            "Max tokens",
            min_value=256,
            max_value=32000,
            value=DEFAULT_MAX_TOKENS,
            step=256,
            key="scene_editor_max_tokens",
        )
        timeout_seconds = st.number_input(
            "Timeout (s)",
            min_value=30,
            max_value=3600,
            value=DEFAULT_TIMEOUT_SECONDS,
            step=30,
            key="scene_editor_timeout_seconds",
        )
    model = custom_model if model_choice == "custom" else model_choice
    settings = GenerationSettings(
        model=model.strip() or DEFAULT_MODEL,
        temperature=float(temperature),
        max_tokens=int(max_tokens),
    )
    ollama_client = OllamaClient(timeout_seconds=int(timeout_seconds))

    base_col, notes_col, draft_col = st.columns(3)
    with base_col:
        st.subheader("Screenplay base")
        render_markdown_with_raw("screenplay base", source.screenplay_markdown)
    with notes_col:
        st.subheader("Notas editoriales")
        render_markdown_with_raw(
            "notas editoriales",
            source.editorial_notes_markdown or "_Sin notas editoriales._",
        )
    with draft_col:
        st.subheader("Draft cinematográfico")
        draft_numbers, selected_draft = select_active_draft(
            root,
            selected_session,
            selected_scene,
        )
        draft_text = selected_draft.response if selected_draft else ""
        if selected_draft:
            st.success(f"Draft activo: {selected_draft.draft_number:03d}")
            st.caption(draft_metadata_text(selected_draft))
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

    previous_draft = previous_draft_for_active(
        root,
        selected_session,
        selected_scene,
        draft_numbers,
        selected_draft,
    )

    st.subheader("Evaluacion rapida")
    if selected_draft:
        eval_col_a, eval_col_b, eval_col_c, eval_col_d = st.columns([1, 1, 1, 3])
        with eval_col_a:
            if st.button("Mejor", use_container_width=True):
                save_draft_evaluation(
                    root,
                    selected_session,
                    selected_scene,
                    selected_draft.draft_number,
                    "better",
                )
                st.rerun()
        with eval_col_b:
            if st.button("Igual", use_container_width=True):
                save_draft_evaluation(
                    root,
                    selected_session,
                    selected_scene,
                    selected_draft.draft_number,
                    "same",
                )
                st.rerun()
        with eval_col_c:
            if st.button("Peor", use_container_width=True):
                save_draft_evaluation(
                    root,
                    selected_session,
                    selected_scene,
                    selected_draft.draft_number,
                    "worse",
                )
                st.rerun()
        with eval_col_d:
            current_eval = EVALUATION_LABELS.get(
                selected_draft.user_evaluation,
                "Sin evaluar",
            )
            st.caption(f"Evaluacion actual: {current_eval}")
    else:
        st.info("Genera un draft antes de evaluar.")

    st.subheader("Comparacion de drafts")
    compare_prev_col, compare_active_col = st.columns(2)
    with compare_prev_col:
        render_draft_panel("Draft anterior", previous_draft)
    with compare_active_col:
        render_draft_panel("Draft actual", selected_draft, active=True)

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
                            source_draft_number=(
                                selected_draft.draft_number if selected_draft else None
                            ),
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
