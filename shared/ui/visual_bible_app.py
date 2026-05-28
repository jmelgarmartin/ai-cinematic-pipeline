"""Streamlit UI for visual bible generation."""

from __future__ import annotations

import json
import sys
import difflib
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
from shared.visual_bible.models import VisualBibleSettings  # noqa: E402
from shared.visual_bible.locked_storage import (  # noqa: E402
    locked_visual_bible_to_markdown,
    locked_visual_bible_path,
    read_locked_visual_bible,
    read_review_history,
    save_locked_visual_bible,
)
from shared.visual_bible.normalizer import locked_visual_bible_to_payload  # noqa: E402
from shared.visual_bible.reviewer import (  # noqa: E402
    build_locked_visual_bible,
    parse_locked_payload,
    render_locked_json,
)
from shared.visual_bible.storage import (  # noqa: E402
    list_series,
    list_sessions,
    load_visual_bible_source,
    read_visual_bible_json,
    read_visual_bible_markdown,
    save_visual_bible,
    series_root,
    visual_bible_paths,
)
from shared.visual_bible.visual_bible_generator import generate_visual_bible  # noqa: E402


MODEL_OPTIONS = ("gemma4:latest", "qwen3:30b", "custom")


def render_character_browser(visual_bible: dict[str, object]) -> None:
    """Render character profiles."""

    characters = visual_bible.get("characters", [])
    if not isinstance(characters, list) or not characters:
        st.info("No hay perfiles de personajes.")
        return
    labels = [str(character.get("character_id", f"character_{index}")) for index, character in enumerate(characters, start=1) if isinstance(character, dict)]
    selected = st.selectbox("Personaje", labels)
    character = next(
        item for item in characters if isinstance(item, dict) and item.get("character_id") == selected
    )
    st.json(character)


def render_environment_browser(visual_bible: dict[str, object]) -> None:
    """Render environment rules."""

    environments = visual_bible.get("environments", [])
    if not isinstance(environments, list) or not environments:
        st.info("No hay reglas de localizaciones.")
        return
    labels = [str(environment.get("location", f"location_{index}")) for index, environment in enumerate(environments, start=1) if isinstance(environment, dict)]
    selected = st.selectbox("Localizacion", labels)
    environment = next(
        item for item in environments if isinstance(item, dict) and item.get("location") == selected
    )
    st.json(environment)


def render_locked_review_panel(
    root: Path,
    session_id: str,
    visual_bible: dict[str, object],
) -> None:
    """Render editable review controls for the locked visual bible."""

    proposed_locked = build_locked_visual_bible(visual_bible)
    proposed_payload = locked_visual_bible_to_payload(proposed_locked)
    existing_payload = read_locked_visual_bible(root, session_id)
    active_payload = existing_payload or proposed_payload
    locked_path = locked_visual_bible_path(root, session_id)

    st.subheader("Visual bible review")
    if existing_payload:
        st.caption(f"Locked: {locked_path.name}")
    else:
        st.caption("Todavia no hay locked visual bible. Se muestra una normalizacion inicial.")

    edit_a, edit_b = st.columns(2)
    with edit_a:
        characters_text = st.text_area(
            "Personajes canonicos",
            json.dumps(active_payload.get("characters", []), ensure_ascii=False, indent=2),
            height=420,
            key=f"locked_characters_{session_id}",
        )
    with edit_b:
        environments_text = st.text_area(
            "Localizaciones canonicas",
            json.dumps(active_payload.get("environments", []), ensure_ascii=False, indent=2),
            height=420,
            key=f"locked_environments_{session_id}",
        )

    note = st.text_input(
        "Nota de revision",
        value="Manual visual consistency lock",
        key=f"locked_note_{session_id}",
    )

    try:
        edited_payload = dict(active_payload)
        edited_payload["characters"] = json.loads(characters_text)
        edited_payload["environments"] = json.loads(environments_text)
        locked = parse_locked_payload(json.dumps(edited_payload, ensure_ascii=False))
        locked_json = render_locked_json(locked)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        st.error(f"JSON de revision invalido: {exc}")
        return

    if locked.validation_warnings:
        st.warning("Validaciones pendientes: " + "; ".join(locked.validation_warnings))
    else:
        st.success("Validaciones OK: sin duplicados ni perfiles visuales vacios.")

    action_a, action_b = st.columns([1, 3])
    with action_a:
        if st.button("Lock Visual Bible", type="primary", use_container_width=True):
            save_locked_visual_bible(root, session_id, locked, note=note)
            st.success(f"Locked visual bible guardada: {locked_path.name}")
            st.rerun()
    with action_b:
        st.caption(
            "El locked JSON elimina prompts y fuentes completas; conserva hashes, "
            "metadata minima e identidad visual canonica."
        )

    preview_a, preview_b = st.columns(2)
    with preview_a:
        st.markdown(locked_visual_bible_to_markdown(locked))
    with preview_b:
        st.json(json.loads(locked_json))

    with st.expander("Diff original normalizado vs locked", expanded=False):
        original = json.dumps(proposed_payload, ensure_ascii=False, indent=2).splitlines()
        current = locked_json.splitlines()
        diff = difflib.unified_diff(
            original,
            current,
            fromfile="visual_bible.normalized.json",
            tofile="visual_bible.locked.json",
            lineterm="",
        )
        st.code("\n".join(diff) or "Sin diferencias.", language="diff")

    history = read_review_history(root, session_id)
    with st.expander("Review history", expanded=False):
        if history:
            st.json(history)
        else:
            st.info("Todavia no hay historial de revision.")


def main() -> None:
    """Render visual bible UI."""

    st.set_page_config(page_title="SeriesIA Visual Bible", layout="wide")
    st.title("SeriesIA Visual Bible")

    series_names = list_series()
    if not series_names:
        st.error("No series directories found.")
        return

    top_series, top_session = st.columns([1.2, 1.8])
    with top_series:
        selected_series = st.selectbox("Serie", series_names)

    root = series_root(selected_series)
    sessions = list_sessions(root)
    if not sessions:
        st.warning("No sessions found with both final screenplay and storyboard breakdown.")
        return

    with top_session:
        selected_session = st.selectbox("Sesion", sessions)

    source = load_visual_bible_source(root, selected_series, selected_session)

    settings_a, settings_b, settings_c, settings_d = st.columns([1.1, 1.4, 1, 1])
    with settings_a:
        model_choice = st.selectbox("Modelo", MODEL_OPTIONS, key="visual_bible_model_choice")
    with settings_b:
        custom_model = st.text_input(
            "Modelo custom",
            value=st.session_state.get("visual_bible_custom_model", DEFAULT_MODEL),
            key="visual_bible_custom_model",
            disabled=model_choice != "custom",
        )
    with settings_c:
        temperature = st.slider(
            "Temperatura",
            0.0,
            1.2,
            DEFAULT_TEMPERATURE,
            0.05,
            key="visual_bible_temperature",
        )
    with settings_d:
        max_tokens = st.number_input(
            "Max tokens",
            min_value=1024,
            max_value=32000,
            value=DEFAULT_MAX_TOKENS,
            step=512,
            key="visual_bible_max_tokens",
        )
        timeout_seconds = st.number_input(
            "Timeout (s)",
            min_value=30,
            max_value=3600,
            value=DEFAULT_TIMEOUT_SECONDS,
            step=30,
            key="visual_bible_timeout_seconds",
        )

    model = custom_model if model_choice == "custom" else model_choice
    settings = VisualBibleSettings(
        model=model.strip() or DEFAULT_MODEL,
        temperature=float(temperature),
        max_tokens=int(max_tokens),
    )
    client = OllamaClient(timeout_seconds=int(timeout_seconds))

    visual_bible_json = read_visual_bible_json(root, selected_session)
    visual_bible_markdown = read_visual_bible_markdown(root, selected_session)
    json_path, md_path = visual_bible_paths(root, selected_session)

    action_a, action_b, action_c = st.columns([1.3, 1.4, 3])
    with action_a:
        button_label = "Regenerar visual bible" if visual_bible_json else "Generar visual bible"
        if st.button(button_label, type="primary", use_container_width=True):
            with st.spinner("Generando visual bible con Ollama..."):
                try:
                    record = generate_visual_bible(
                        source=source,
                        settings=settings,
                        client=client,
                    )
                    save_visual_bible(root, selected_session, record)
                    st.success(f"Visual bible guardada: {json_path.name}")
                    st.rerun()
                except (OllamaError, ValueError, json.JSONDecodeError) as exc:
                    st.error(str(exc))
                except Exception as exc:  # pragma: no cover - UI guardrail
                    st.error(f"Error inesperado generando visual bible: {exc}")
    with action_b:
        st.caption(f"JSON: {json_path.name}")
        st.caption(f"Markdown: {md_path.name}")
    with action_c:
        if visual_bible_json:
            metadata = visual_bible_json.get("metadata", {})
            if isinstance(metadata, dict):
                st.caption(
                    f"Modelo: {metadata.get('model', '')} | "
                    f"Prompt: {metadata.get('prompt_version', '')} | "
                    f"Generado: {metadata.get('timestamp', '')}"
                )

    storyboard_col, bible_col = st.columns(2)
    with storyboard_col:
        st.subheader("Storyboard")
        st.text_area(
            "Storyboard source",
            source.storyboard_json_text,
            height=720,
            disabled=True,
            label_visibility="collapsed",
        )

    with bible_col:
        st.subheader("Visual bible")
        if not visual_bible_json:
            st.info("Todavia no hay visual bible para esta sesion.")
        else:
            tabs = st.tabs(
                [
                    "Personajes",
                    "Localizaciones",
                    "Review",
                    "Fotografia",
                    "Color",
                    "Iluminacion",
                    "Referencias",
                    "Reglas",
                ]
            )
            with tabs[0]:
                render_character_browser(visual_bible_json)
            with tabs[1]:
                render_environment_browser(visual_bible_json)
            with tabs[2]:
                render_locked_review_panel(root, selected_session, visual_bible_json)
            cinematography = visual_bible_json.get("cinematography", {})
            identity = visual_bible_json.get("series_visual_identity", {})
            with tabs[3]:
                if isinstance(cinematography, dict):
                    st.json(
                        {
                            "camera_language": cinematography.get("camera_language", {}),
                            "composition": cinematography.get("composition", {}),
                            "lenses": cinematography.get("lenses", {}),
                            "texture": cinematography.get("texture", {}),
                        }
                    )
            with tabs[4]:
                if isinstance(cinematography, dict):
                    st.json(cinematography.get("color_grading", {}))
            with tabs[5]:
                if isinstance(cinematography, dict):
                    st.json(cinematography.get("lighting", {}))
            with tabs[6]:
                if isinstance(identity, dict):
                    st.json(
                        {
                            "references": identity.get("references", []),
                            "visual_keywords": identity.get("visual_keywords", []),
                        }
                    )
            with tabs[7]:
                if isinstance(identity, dict):
                    st.json(identity.get("visual_rules", []))

    with st.expander("Visual bible markdown", expanded=False):
        if visual_bible_markdown:
            st.markdown(visual_bible_markdown)
        else:
            st.info("Todavia no hay markdown de visual bible.")

    with st.expander("Visual bible JSON", expanded=False):
        if visual_bible_json:
            st.json(visual_bible_json)
        else:
            st.info("Todavia no hay JSON de visual bible.")

    with st.expander("Final screenplay source", expanded=False):
        st.markdown(source.final_screenplay_markdown)


if __name__ == "__main__":
    main()
