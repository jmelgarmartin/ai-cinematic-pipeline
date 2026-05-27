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
