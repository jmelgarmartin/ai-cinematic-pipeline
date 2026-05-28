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
ollama pull gemma4:latest
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

Flujo editorial:

- El panel superior muestra screenplay base, notas editoriales y draft activo.
- La seccion de comparacion muestra automaticamente el draft anterior junto al
  draft actual.
- Cada panel de draft muestra numero, modelo, temperatura, timestamp y version
  de prompt.
- Los expanders permiten revisar el texto raw.
- Los botones `Mejor`, `Igual` y `Peor` guardan `user_evaluation` en el JSON del
  draft activo y anaden un evento a `conversation_history.json`.

## Modelos recomendados

`gemma4:latest` es el modelo recomendado para escritura cinematografica y
screenplay atmosferico. En las pruebas locales sigue mejor las instrucciones de
salida limpia y evita mejor el reasoning visible.

`qwen3:30b` permanece disponible desde el selector de modelo. Puede ser util en
tareas de refinamiento, pero se ha observado reasoning residual tipo
`Okay, the user...` incluso usando `think=false` y `/no_think`. La UI y el
pipeline limpian preambulos cuando pueden, pero Qwen es menos fiable para
salida directa.

Privacidad:

- Drafts, conversaciones y finales son outputs privados en `processing/`.
- No se versionan prompts ni respuestas reales.
- El modelo es configurable desde la UI; el valor por defecto vive en
  `shared/scene_editor/config.py`.
- El output esperado es una escena cinematografica final, no analisis ni
  razonamiento visible.
- Se recomiendan modelos instruct o no-reasoning. Si se usa un modelo reasoning
  como Qwen, puede requerir limpieza adicional o configuracion especifica.

Limitaciones actuales:

- Requiere Ollama levantado localmente.
- No hace evaluacion automatica de calidad.
- No comprueba continuidad entre escenas.
- La limpieza defensiva recorta preambulos tipo chatbot cuando detecta un
  encabezado valido de escena.

## storyboard_app.py

Interfaz experimental para convertir una escena aceptada de `final_screenplay`
en un desglose estructurado de storyboard audiovisual.

Arranque:

```powershell
uv run streamlit run .\shared\ui\storyboard_app.py
```

La app lee:

- `<serie>/processing/final_screenplay/<session>/escena_XXX.final.md`

La app escribe:

- `<serie>/processing/storyboard_breakdown/<session>/escena_XXX.storyboard.json`
- `<serie>/processing/storyboard_breakdown/<session>/escena_XXX.storyboard.md`

La app permite:

- Seleccionar serie, sesion y escena final.
- Generar o regenerar el storyboard con Ollama.
- Navegar shots.
- Ver final screenplay, markdown de storyboard y JSON.
- Revisar metadata de modelo, timestamp y version de prompt.

Esta fase no genera imagenes, no genera prompts artisticos finales y no produce
animacion. El objetivo es continuidad visual, division en beats y planificacion
de shots para una futura fase de image prompts.

## visual_bible_app.py

Interfaz experimental para generar una biblia visual reutilizable a partir de
`final_screenplay` y `storyboard_breakdown`.

Arranque:

```powershell
uv run streamlit run .\shared\ui\visual_bible_app.py
```

La app lee:

- `<serie>/processing/final_screenplay/<session>/*.final.md`
- `<serie>/processing/storyboard_breakdown/<session>/*.storyboard.json`

La app escribe:

- `<serie>/processing/visual_bible/<session>/visual_bible.json`
- `<serie>/processing/visual_bible/<session>/visual_bible.md`

La app permite:

- Seleccionar serie y sesion.
- Generar o regenerar la visual bible con Ollama.
- Navegar perfiles de personajes.
- Navegar localizaciones.
- Revisar fotografia, color, iluminacion, referencias y reglas visuales.
- Ver JSON y Markdown.

Esta fase existe antes de image prompts para fijar consistencia visual. No
genera imagenes, no genera prompts finales de Stable Diffusion y no produce
animacion.
