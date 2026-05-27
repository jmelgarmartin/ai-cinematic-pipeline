# Scripts

## 00_split_full_session.py

Divide un transcript completo de una sesion en escenas candidatas usando parsing y heuristicas deterministas. No limpia dialogos, no resume contenido y no usa LLMs: conserva las lineas originales y solo decide posibles cortes de escena.

Uso desde la raiz de la serie:

```powershell
uv run python .\scripts\00_split_full_session.py .\input\raw_sessions\sesion_01.txt
```

El script genera archivos `escena_XXX.txt` y `scenes_index.json` en `processing/scene_candidates/`.

Limitaciones actuales:

- Las localizaciones, saltos temporales y eventos se detectan por palabras clave.
- El resultado es una primera segmentacion candidata, no una escena final validada.
- El metajuego y comentarios fuera de personaje se conservan sin clasificar.

Mejoras futuras posibles:

- Configuracion externa de heuristicas por serie.
- Tests automatizados con transcripts de ejemplo.
- Deteccion mas fina de cambios de foco narrativo.
- Integracion posterior con limpieza de transcript y extraccion de escenas.
