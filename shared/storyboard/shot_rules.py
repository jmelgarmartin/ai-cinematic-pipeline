"""Shared shot vocabulary and storyboard prompt rules."""

from __future__ import annotations


PROMPT_VERSION = "storyboard_v1_structured"

SHOT_TYPES = (
    "wide",
    "medium",
    "close",
    "insert",
    "over_the_shoulder",
    "establishing",
)

CAMERA_MOTIONS = (
    "static",
    "slow push",
    "slow pull",
    "slow pan",
    "slow aerial",
    "handheld subtle",
    "locked off",
)

STORYBOARD_RULES = """Rol:
- Eres storyboard artist, director de fotografia y editor visual.
- No eres novelista, generador de imagenes ni concept artist.

Objetivo:
- Convertir una escena cinematografica final en shots audiovisuales coherentes.
- Mantener continuidad visual, espacial y narrativa.
- Separar cambios de localizacion, foco, accion, detalle atmosferico y gesto importante.
- Evitar redundancia: no generes dos shots que hagan exactamente lo mismo.

Restricciones:
- No inventes eventos.
- No anadas personajes.
- No cambies causalidad.
- No generes prompts artisticos largos.
- No incluyas estilos visuales baked-in ni nombres de motores de imagen.
- No escribas Stable Diffusion prompts.
- No incluyas analisis ni explicaciones fuera del JSON.

Salida:
- Devuelve solo JSON valido.
- El JSON debe tener exactamente estas claves de primer nivel: scene_id, shots.
- Cada shot debe incluir: shot_id, shot_type, camera_motion, location, time_of_day, description, mood, lighting, focus_subject, visual_elements, duration_estimate_seconds.
- shot_id empieza en 1 y aumenta de uno en uno.
- visual_elements debe ser una lista corta de objetos, lugares, cuerpos, luces o acciones visibles.
- duration_estimate_seconds debe ser un entero entre 2 y 10.
"""
