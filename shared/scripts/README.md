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
- `meta_game`
- `dice_roll`
- `table_talk`
- `unclear`

`SPEAKER_00` puede ser narrador/director o estar interpretando un PNJ. Cuando detecta atribuciones como `Mary dice...`, `Mary: ...` o `la mujer susurra: "..."`, el tipo pasa a `npc_dialogue` y se añade `npc_name` cuando puede extraerse sin inventarlo.

El comando es idempotente. Registra el SHA-256 de la carpeta de escenas candidatas en `<serie>/processing/metadata/cleaned_sessions.json`; si el contenido ya fue procesado, muestra `Cleaned session already processed. Use --force to regenerate.` y termina sin reescribir.

Limitaciones actuales:

- La clasificacion es heuristica y conservadora.
- No resuelve identidades reales de personajes.
- La deteccion de `npc_dialogue` depende de atribuciones explicitas y puede no capturar dialogo indirecto o voces sin nombre.
- No elimina ni normaliza bromas, tiradas, interrupciones ni dudas de reglas.
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

- `meta_game`
- `dice_roll`
- `table_talk`

`unclear` no entra en el guion principal y se coloca al final de cada escena en `REVIEW_REQUIRED` para revision manual.

Limitaciones actuales:

- No mejora estilo ni corrige transcripcion.
- Los nombres de personajes se resuelven con un mapeo simple de speakers.
- La integracion futura con LLMs deberia trabajar sobre este markdown o sobre los JSON limpios, manteniendo trazabilidad.
