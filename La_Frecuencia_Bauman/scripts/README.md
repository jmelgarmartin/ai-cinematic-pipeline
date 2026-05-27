# Scripts especificos de La_Frecuencia_Bauman

Esta carpeta queda reservada para overrides, utilidades puntuales o scripts que solo tengan sentido para esta serie.

Las herramientas reutilizables del pipeline viven en `shared/scripts/`. Para dividir una sesion en escenas candidatas usa:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman"
```

O indicando un transcript concreto:

```powershell
uv run python .\shared\scripts\split_full_session.py --series "La_Frecuencia_Bauman" --input ".\La_Frecuencia_Bauman\input\raw_sessions\sesion_01.txt"
```
