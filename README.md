# SeriesIA

SeriesIA es un entorno reproducible para scripts de pipeline de series creadas con asistencia de IA. Este proyecto prepara la organizacion, configuracion y dependencias base de Python, sin instalar todavia ComfyUI, modelos pesados, CUDA ni herramientas de audio/video de alto peso.

## Estructura

```text
SeriesIA/
  create_series.py
  pyproject.toml
  uv.lock
  shared/
  Nombre_De_La_Serie/
```

`shared/` contiene recursos reutilizables entre series: workflows, prompts, plantillas, musica, efectos, voces, overlays, scripts, cache y documentacion de modelos.

Cada carpeta de serie contiene su propio material de entrada, procesamiento, assets, video, audio, scripts y configuracion. Las series se crean al mismo nivel que `shared/`, no dentro de otra carpeta `SeriesIA`.

Los datos reales de partidas no se versionan: transcripts, subtitulos, audio, referencias, assets privados y outputs intermedios quedan ignorados por git. Los resultados generados en `processing/scene_candidates/` y el registro `processing/metadata/processed_sessions.json` son estado privado del pipeline.

## Crear una serie

```powershell
uv run python create_series.py "Nombre_De_La_Serie"
```

El comando crea la estructura esperada para una serie nueva y respeta carpetas o archivos existentes.

## Dependencias

Sincroniza el entorno con:

```powershell
uv sync
```

Ejecuta scripts con:

```powershell
uv run python <script>
```

Por ejemplo:

```powershell
uv run python create_series.py "La_Frecuencia_Bauman"
```

Herramientas globales del pipeline:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman"
```

El splitter es idempotente: si el mismo archivo ya fue procesado con el mismo SHA-256, no vuelve a generar escenas. Para regenerar de forma explicita:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman" --force
```

Tambien puedes indicar un transcript concreto:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman" --input ".\La_Frecuencia_Bauman\input\raw_sessions\sesion_01.txt"
```

El output se escribe por sesion en:

```text
<serie>/processing/scene_candidates/<session_stem>/
```

## Editorial notes

`editorial_notes/` es una capa humana opcional por serie y por sesion. Permite
anotar cada escena antes de una futura seleccion editorial o reescritura
asistida, sin modificar el screenplay original.

Las notas reales de una serie se guardan en:

```text
<serie>/editorial_notes/<session_stem>/escena_001.notes.md
```

El script global aplica esas notas sobre el screenplay ya generado:

```powershell
uv run python .\shared\scripts\apply_editorial_notes.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54"
```

Genera JSON anotado en `<serie>/processing/annotated_screenplay/<session_stem>/`.
El resultado mantiene hashes SHA-256, rutas de origen y trazabilidad hacia el
screenplay y el archivo de notas. Esta fase no usa LLMs y prepara la entrada
para un futuro `scene_editor` o LLM local.

Las notas editoriales reales y los outputs anotados se consideran datos privados
de trabajo y no se versionan por defecto. Hay un ejemplo versionable en
`docs/examples/editorial_notes_example.md`.

## Editorial notes bootstrap

Para empezar una ronda editorial, genera plantillas vacias para todas las escenas
disponibles en el screenplay de una sesion:

```powershell
uv run python .\shared\scripts\init_editorial_notes.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54"
```

El comando crea un archivo `escena_XXX.notes.md` por cada escena existente. Es
idempotente: si una nota ya existe, no la sobrescribe salvo que se use `--force`.

Flujo esperado:

```text
processing/screenplay/<session>/
  -> editorial_notes/<session>/
  -> processing/annotated_screenplay/<session>/
```

`screenplay` es el guion estructurado generado por la pipeline.
`editorial_notes` es la capa humana privada donde se decide que eliminar,
mantener, que planos sugerir y cual es la intencion de la escena.
`annotated_screenplay` combina ambos sin alterar los originales y prepara una
entrada trazable para futuras herramientas editoriales o LLMs locales.

Ejemplo completo de nota editada:
`docs/examples/generated_editorial_note_example.md`.

## Editorial UI

La interfaz editorial local permite revisar cada escena, comparar el screenplay
base con sus notas editoriales, guardar cambios y aplicar las notas para generar
`annotated_screenplay`.

Arranque:

```powershell
uv run streamlit run .\shared\ui\editorial_app.py
```

Flujo recomendado:

1. Generar `processing/screenplay/<session>/`.
2. Inicializar notas con `init_editorial_notes.py`.
3. Abrir la UI de Streamlit.
4. Editar escena por escena.
5. Aplicar notas desde la UI o con `apply_editorial_notes.py`.
6. Revisar `processing/annotated_screenplay/<session>/`.

La UI no modifica el screenplay base. Solo escribe notas privadas en
`editorial_notes/` y reutiliza la fase de anotacion existente para generar los
JSON anotados.

## Scene editor LLM

El scene editor es una fase experimental para convertir `annotated_screenplay`
en borradores cinematograficos iterativos usando un LLM local con Ollama. Mantiene
separacion entre fuentes y generados: no modifica `screenplay`, `editorial_notes`
ni `annotated_screenplay`.

Arranca Ollama y descarga el modelo deseado, por ejemplo:

```powershell
ollama serve
ollama pull gemma4:latest
```

Para esta fase se recomiendan modelos instruct o no-reasoning. Los modelos de
razonamiento, como algunas variantes de Qwen, pueden devolver reasoning visible
tipo `Okay, let's...` o `First, I need...`. El editor incluye limpieza defensiva,
pero el output esperado siempre es una escena final, no analisis ni informe.

### Modelos recomendados

`gemma4:latest` es el modelo recomendado por defecto para reescritura de
screenplay atmosferico: tiende a seguir mejor el tono cinematografico y produce
menos trazas de razonamiento visibles.

`qwen3:30b` sigue siendo configurable y puede resultar util para refinamientos
complejos, pero en pruebas locales ha sido menos fiable ocultando reasoning:
incluso con `think=false` y `/no_think`, algunas respuestas pueden empezar con
texto tipo `Okay, the user...`. El scene editor intenta limpiar esos preambulos,
pero para trabajo editorial fluido se recomienda empezar con Gemma.

La UI local se abre con:

```powershell
uv run streamlit run .\shared\ui\scene_editor_app.py
```

Flujo completo:

1. Generar `processing/screenplay/<session>/`.
2. Inicializar y editar `editorial_notes/<session>/`.
3. Aplicar notas para crear `processing/annotated_screenplay/<session>/`.
4. Abrir el scene editor.
5. Generar un primer draft con Ollama.
6. Comparar el draft activo con el anterior.
7. Marcar rapidamente si el draft es mejor, igual o peor.
8. Refinar con instrucciones adicionales sin perder trazabilidad.
9. Guardar una version aceptada como final.

Los drafts se guardan en:

```text
<serie>/processing/final_screenplay/<session>/drafts/<scene_id>/
```

La version final aceptada se guarda en:

```text
<serie>/processing/final_screenplay/<session>/escena_001.final.md
<serie>/processing/final_screenplay/<session>/escena_001.final.json
```

Cada draft conserva prompt, respuesta, modelo, temperatura, feedback, draft de
origen, evaluacion editorial manual, hashes de origen, timestamp, version de
prompt y si hubo limpieza de salida. `conversation_history.json` guarda eventos
legibles de generacion y evaluacion. Estos outputs son privados y no se
versionan.

## Storyboard breakdown

`storyboard_breakdown` es la siguiente fase despues de `final_screenplay`.
Convierte una escena cinematografica final aceptada en una estructura de shots
para planificacion audiovisual.

Esta fase no genera imagenes, no genera prompts artisticos finales, no usa
Stable Diffusion y no produce animacion. Solo analiza el screenplay final,
divide la escena en beats visuales y guarda shots coherentes con continuidad
espacial y narrativa.

Entrada:

```text
<serie>/processing/final_screenplay/<session>/escena_001.final.md
```

Salida privada:

```text
<serie>/processing/storyboard_breakdown/<session>/escena_001.storyboard.json
<serie>/processing/storyboard_breakdown/<session>/escena_001.storyboard.md
```

La UI local se abre con:

```powershell
uv run streamlit run .\shared\ui\storyboard_app.py
```

Flujo previsto:

```text
screenplay
  -> final_screenplay
  -> storyboard_breakdown
  -> image prompts
  -> images
  -> animation
```

El JSON de storyboard conserva shots, prompt, modelo, timestamp, hashes y
version de prompt (`storyboard_v1_structured`). Los outputs siguen siendo datos
privados de trabajo y no se versionan.

## Entorno en PowerShell

Normalmente no hace falta activar el entorno si usas `uv run`. Si quieres activarlo manualmente:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activacion por `ExecutionPolicy`, no cambies la politica global sin revisarlo antes. Opciones habituales:

Opcion recomendada para el usuario actual:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Opcion temporal para abrir una sesion con bypass:

```powershell
powershell -ExecutionPolicy Bypass
```

## Fuera de este entorno

Por ahora ComfyUI, modelos pesados, modelos de imagen/video/audio, CUDA y herramientas grandes como pipelines de render o transcripcion avanzada se gestionaran fuera de este entorno Python base.

## Next Steps

Las siguientes fases previstas del pipeline son:

- Seleccion editorial de escenas a partir de candidatos y guiones estructurados.
- Mejora cinematografica del material seleccionado.
- Generacion de storyboard y prompts visuales.
- Integracion posterior con generacion de imagen.
- Pipeline de animacion y montaje audiovisual.
- Integracion futura con LLMs manteniendo trazabilidad y reproducibilidad.
