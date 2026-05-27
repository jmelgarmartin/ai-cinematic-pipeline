# Pipeline scripts

`shared/scripts/` contiene herramientas globales reutilizables por cualquier serie.

## split_full_session.py

Divide un transcript completo de una sesion en escenas candidatas usando parsing y heuristicas deterministas. No limpia dialogos, no resume contenido y no usa LLMs: conserva las lineas originales y solo decide posibles cortes de escena.

Uso automatico con el transcript mas reciente de la serie:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman"
```

El comando es idempotente. Registra cada archivo por SHA-256 en `<serie>/processing/metadata/processed_sessions.json`; si el mismo contenido ya fue procesado, muestra `Session already processed. Use --force to regenerate.` y termina sin reescribir escenas.

Para reprocesar:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman" --force
```

Uso indicando un archivo concreto:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman" --input ".\La_Frecuencia_Bauman\input\raw_sessions\sesion_01.txt"
```

El script busca transcripts `.txt`, `.srt` o `.json` en `<serie>/input/raw_sessions/` y genera `escena_XXX.txt` y `scenes_index.json` en `<serie>/processing/scene_candidates/<session_stem>/`.

Los transcripts reales, escenas candidatas y metadata de procesado son datos privados de trabajo y no se versionan por defecto.

Limitaciones actuales:

- Las localizaciones, saltos temporales y eventos se detectan por palabras clave.
- El resultado es una primera segmentacion candidata, no una escena final validada.
- El metajuego y comentarios fuera de personaje se conservan sin clasificar.

## clean_transcript.py

Convierte escenas candidatas de texto en JSON estructurado por entradas. Este paso no borra texto, no limpia metajuego y no genera guion cinematografico; solo parsea, clasifica y etiqueta contenido.

Uso automatico con la sesion de escenas candidatas mas reciente:

```powershell
uv run python .\shared\scripts\clean_transcript.py --series "La_Frecuencia_Bauman"
```

Para reprocesar:

```powershell
uv run python .\shared\scripts\clean_transcript.py --series "La_Frecuencia_Bauman" --force
```

Tambien acepta una sesion concreta:

```powershell
uv run python .\shared\scripts\clean_transcript.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54"
```

Lee desde `<serie>/processing/scene_candidates/<session_stem>/` y escribe en `<serie>/processing/cleaned_transcripts/<session_stem>/`.

Tipos soportados:

- `description`
- `dialogue`
- `npc_dialogue`
- `player_intent`
- `player_question`
- `rules_meta`
- `table_talk`
- `post_session_feedback`
- `mixed_entry`
- `unclear`

`dialogue` es extremadamente conservador: solo debe representar frases que parecen dichas por el personaje dentro de la ficcion. `player_intent` representa acciones declaradas por jugadores, y `player_question` representa preguntas al master o preguntas sobre posibilidades de accion.

`post_session_feedback` separa comentarios de cierre, estrellas/deseos, analisis de personajes y charla sobre la partida o el capitulo. Tiene prioridad alta para que ese material no contamine el screenplay.

`mixed_entry` marca entradas con varios modos narrativos mezclados, por ejemplo dialogo, accion, intencion y descripcion en una misma linea. No se divide automaticamente todavia: se conserva completa para una futura capa editorial o LLM.

`SPEAKER_00` puede ser narrador/director o estar interpretando un PNJ. Cuando detecta atribuciones como `Mary dice...`, `Mary: ...` o `la mujer susurra: "..."`, el tipo pasa a `npc_dialogue` y se añade `npc_name` cuando puede extraerse sin inventarlo.

El comando es idempotente. Registra el SHA-256 de la carpeta de escenas candidatas en `<serie>/processing/metadata/cleaned_sessions.json`; si el contenido ya fue procesado, muestra `Cleaned session already processed. Use --force to regenerate.` y termina sin reescribir.

Limitaciones actuales:

- La clasificacion es heuristica y conservadora.
- No resuelve identidades reales de personajes.
- La deteccion de `npc_dialogue` depende de atribuciones explicitas y puede no capturar dialogo indirecto o voces sin nombre.
- No elimina ni normaliza bromas, tiradas, interrupciones ni dudas de reglas.
- El pipeline sigue siendo determinista y reversible: cada entrada conserva `raw_line`, `text`, `speaker`, `line_number` y `entry_id`.
- Futuras mejoras: configuracion externa por serie, tests con fixtures y reglas mas finas para dialogo en personaje.

## build_screenplay.py

Renderiza `cleaned_transcripts` como markdown de guion cinematografico legible. No reescribe, no resume, no embellece y no usa LLMs: solo ordena y formatea contenido ya clasificado.

Uso automatico con la sesion limpia mas reciente:

```powershell
uv run python .\shared\scripts\build_screenplay.py --series "La_Frecuencia_Bauman"
```

Para reprocesar:

```powershell
uv run python .\shared\scripts\build_screenplay.py --series "La_Frecuencia_Bauman" --force
```

Tambien acepta una sesion concreta:

```powershell
uv run python .\shared\scripts\build_screenplay.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54"
```

Lee desde `<serie>/processing/cleaned_transcripts/<session_stem>/` y escribe `.md` en `<serie>/processing/screenplay/<session_stem>/`.

Tipos incluidos:

- `description` pasa a la seccion `DESCRIPTION`.
- `dialogue` y `npc_dialogue` pasan a la seccion `DIALOGUE`.

Tipos excluidos del guion principal:

- `rules_meta`
- `table_talk`
- `post_session_feedback`

`player_intent` y `player_question` no entran en el guion principal, pero se conservan en secciones `PLAYER_INTENT` y `PLAYER_QUESTION`. `mixed_entry` se conserva en `MIXED_ENTRIES` porque requiere revision editorial antes de separarse. `unclear` se coloca al final de cada escena en `REVIEW_REQUIRED` para revision manual.

Limitaciones actuales:

- No mejora estilo ni corrige transcripcion.
- Los nombres de personajes se resuelven con un mapeo simple de speakers.
- La integracion futura con LLMs deberia trabajar sobre este markdown o sobre los JSON limpios, manteniendo trazabilidad.

## build_review_report.py

Genera un informe manual de entradas `unclear` a partir de `cleaned_transcripts`. No cambia clasificaciones ni modifica los JSON existentes; sirve para detectar patrones reales y mejorar reglas heuristicas.

Uso automatico con la sesion limpia mas reciente:

```powershell
uv run python .\shared\scripts\build_review_report.py --series "La_Frecuencia_Bauman"
```

Tambien acepta una sesion concreta:

```powershell
uv run python .\shared\scripts\build_review_report.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54"
```

Lee desde `<serie>/processing/cleaned_transcripts/<session_stem>/` y escribe en `<serie>/processing/review_reports/<session_stem>/`.

Archivos generados:

- `unclear_entries.md`: informe legible agrupado por escena, con speaker, linea, texto y raw line.
- `review_index.json`: resumen con totales, speakers afectados y frases iniciales frecuentes.

## apply_editorial_notes.py

Aplica notas editoriales humanas sobre el screenplay generado y produce JSON
anotado para fases posteriores. No modifica los `.md` originales, no reescribe
texto y no usa LLMs.

Uso con una sesion concreta:

```powershell
uv run python .\shared\scripts\apply_editorial_notes.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54"
```

Para regenerar:

```powershell
uv run python .\shared\scripts\apply_editorial_notes.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54" --force
```

Lee desde `<serie>/processing/screenplay/<session_stem>/` y busca notas en
`<serie>/editorial_notes/<session_stem>/`. Si una escena no tiene notas, genera
igualmente el JSON con listas vacias.

Formato de notas soportado:

```markdown
# escena_001

## Eliminar
- Texto libre

## Mantener
- Texto libre

## Planos sugeridos
- Texto libre

## Intención
Texto libre
```

El output privado se escribe en
`<serie>/processing/annotated_screenplay/<session_stem>/` e incluye un
`annotated_index.json`. Cada escena conserva el markdown original, las notas
parseadas, hashes SHA-256 del screenplay y de las notas, y rutas relativas para
trazabilidad.

## init_editorial_notes.py

Genera plantillas vacias de notas editoriales para cada escena disponible en una
sesion de screenplay. Es una ayuda para iniciar la revision humana sin tocar el
screenplay original.

Inicializar notas:

```powershell
uv run python .\shared\scripts\init_editorial_notes.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54"
```

El comando lee `<serie>/processing/screenplay/<session_stem>/`, ignora
`screenplay_index.json` y crea archivos en
`<serie>/editorial_notes/<session_stem>/`.

Formato generado:

```markdown
# escena_001

## Eliminar

## Mantener

## Planos sugeridos

## Intención
```

Es idempotente: omite notas existentes y solo las sobrescribe con `--force`.
El resumen final indica escenas creadas, omitidas y sobrescritas.

Despues de editar las notas, se aplican con:

```powershell
uv run python .\shared\scripts\apply_editorial_notes.py --series "La_Frecuencia_Bauman" --session "dialogos_2026-01-22 18-06-54"
```

La interfaz local de Streamlit en `shared/ui/editorial_app.py` complementa estos
scripts: permite navegar escenas, editar notas, guardarlas y aplicar la fase de
anotacion desde una UI local.
