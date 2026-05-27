# Pipeline scripts

`shared/scripts/` contiene herramientas globales reutilizables por cualquier serie.

## split_full_session.py

Divide un transcript completo de una sesion en escenas candidatas usando parsing y heuristicas deterministas. No limpia dialogos, no resume contenido y no usa LLMs: conserva las lineas originales y solo decide posibles cortes de escena.

Uso automatico con el transcript mas reciente de la serie:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman"
```

Uso indicando un archivo concreto:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman" --input ".\La_Frecuencia_Bauman\input\raw_sessions\sesion_01.txt"
```

El script busca transcripts `.txt`, `.srt` o `.json` en `<serie>/input/raw_sessions/` y genera `escena_XXX.txt` y `scenes_index.json` en `<serie>/processing/scene_candidates/`.

Limitaciones actuales:

- Las localizaciones, saltos temporales y eventos se detectan por palabras clave.
- El resultado es una primera segmentacion candidata, no una escena final validada.
- El metajuego y comentarios fuera de personaje se conservan sin clasificar.
