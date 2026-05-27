"""Prompt construction for the local cinematic scene editor."""

from __future__ import annotations

from .models import SceneSource


BASE_SYSTEM_INSTRUCTIONS = """Eres un editor cinematografico para una serie narrativa.
Tu trabajo es transformar material estructurado en una escena cinematografica clara,
visual y producible.

Restricciones obligatorias:
- No inventes lore.
- No anadas personajes.
- No cambies la causalidad de los hechos.
- Mantén el tono y la intencion emocional.
- Convierte exposicion en imagen, accion y subtexto cuando sea posible.
- Elimina metajuego, reglas, tiradas y conversacion de mesa.
- Conserva la informacion importante del screenplay y de las notas.
- Si falta informacion, no la rellenes con hechos nuevos.
- Entrega solo la escena reescrita en markdown.

Contrato de salida:
- Empieza directamente con la escena.
- No escribas titulos como "Revision", "Optimizacion", "Objetivo" o similares.
- No expliques lo que vas a hacer.
- No incluyas analisis, comentarios editoriales ni justificacion.
- No uses frases como "A continuacion", "Presento una version" o "El guion actual".
- No uses separadores decorativos como "---".
- No dividas la respuesta en propuesta, revision o recomendaciones.
- El output debe ser utilizable como borrador final de screenplay, no como informe.
"""


def build_initial_prompt(source: SceneSource) -> str:
    """Build the first-generation prompt for a scene."""

    return f"""{BASE_SYSTEM_INSTRUCTIONS}

# TAREA
Genera un primer borrador cinematografico final para la escena `{source.scene_id}`.
La primera linea de tu respuesta debe pertenecer a la escena, no a una explicacion.

# SCREENPLAY BASE
{source.screenplay_markdown}

# NOTAS EDITORIALES
{source.editorial_notes_markdown or "_Sin notas editoriales._"}

# ANNOTATED SCREENPLAY JSON
{source.annotated_json or "_No existe annotated_screenplay para esta escena._"}
"""


def build_refinement_prompt(
    source: SceneSource,
    previous_draft: str,
    user_feedback: str,
) -> str:
    """Build a refinement prompt that keeps the previous draft in context."""

    return f"""{BASE_SYSTEM_INSTRUCTIONS}

# TAREA
Refina el borrador existente de la escena `{source.scene_id}` usando el feedback
nuevo. No reinicies desde cero: conserva lo que funcione del borrador anterior.
La primera linea de tu respuesta debe pertenecer a la escena refinada, no a una explicacion.

# SCREENPLAY BASE ORIGINAL
{source.screenplay_markdown}

# NOTAS EDITORIALES
{source.editorial_notes_markdown or "_Sin notas editoriales._"}

# BORRADOR ANTERIOR
{previous_draft}

# FEEDBACK NUEVO
{user_feedback or "_Sin feedback adicional._"}
"""
