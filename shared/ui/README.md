# Editorial UIs

Interfaz local de Streamlit para revisar escenas de screenplay y editar notas
editoriales por escena.

## editorial_app.py

Arranque:

```powershell
uv run streamlit run .\shared\ui\editorial_app.py
```

La app lee:

- `<serie>/processing/screenplay/<session>/escena_XXX.md`
- `<serie>/processing/annotated_screenplay/<session>/escena_XXX.annotated.json`

La app escribe:

- `<serie>/editorial_notes/<session>/escena_XXX.notes.md`

Privacidad:

- Las notas reales en `editorial_notes/` no se versionan.
- Los screenplays y annotated screenplays generados en `processing/` tampoco se
  versionan.
- La app trabaja solo con archivos locales.

Limitaciones actuales:

- No usa LLMs.
- No valida semanticamente las notas.
- Aplica notas para toda la sesion usando la logica de
  `shared/scripts/apply_editorial_notes.py`.

## scene_editor_app.py

Interfaz experimental para generar y revisar borradores cinematograficos con un
LLM local mediante Ollama.

Arranca Ollama y descarga el modelo:

```powershell
ollama serve
ollama pull qwen3:30b
```

Arranque de la UI:

```powershell
uv run streamlit run .\shared\ui\scene_editor_app.py
```

La app lee:

- `<serie>/processing/screenplay/<session>/escena_XXX.md`
- `<serie>/editorial_notes/<session>/escena_XXX.notes.md`
- `<serie>/processing/annotated_screenplay/<session>/escena_XXX.annotated.json`

La app escribe:

- `<serie>/processing/final_screenplay/<session>/drafts/<scene_id>/draft_XXX.md`
- `<serie>/processing/final_screenplay/<session>/drafts/<scene_id>/draft_XXX.json`
- `<serie>/processing/final_screenplay/<session>/drafts/<scene_id>/conversation_history.json`
- `<serie>/processing/final_screenplay/<session>/escena_XXX.final.md`
- `<serie>/processing/final_screenplay/<session>/escena_XXX.final.json`

Privacidad:

- Drafts, conversaciones y finales son outputs privados en `processing/`.
- No se versionan prompts ni respuestas reales.
- El modelo es configurable desde la UI; el valor por defecto vive en
  `shared/scene_editor/config.py`.

Limitaciones actuales:

- Requiere Ollama levantado localmente.
- No hace evaluacion automatica de calidad.
- No comprueba continuidad entre escenas.
