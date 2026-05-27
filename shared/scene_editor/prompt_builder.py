"""Prompt construction for the local cinematic scene editor."""

from __future__ import annotations

from .models import SceneSource


PROMPT_VERSION = "scene_editor_v2_no_reasoning"

BASE_SYSTEM_INSTRUCTIONS = """Eres un editor cinematografico profesional.
Tu unica tarea es transformar la escena base y las notas editoriales en una
escena audiovisual final, limpia y producible.

Restricciones obligatorias:
- Responde siempre en espanol.
- Devuelve unicamente la escena cinematografica final.
- No expliques tus decisiones.
- No muestres razonamiento.
- No hables al usuario.
- No analices la tarea.
- No escribas introducciones.
- No uses frases tipo "Okay", "First", "Let's", "I need to" o "The user".
- No devuelvas comentarios sobre el proceso.
- Si produces texto meta o reasoning, la salida es invalida.
- No inventes lore.
- No anadas personajes.
- No cambies la causalidad de los hechos.
- Manten el tono y la intencion emocional.
- Convierte exposicion en imagen, accion y subtexto cuando sea posible.
- Elimina metajuego, reglas, tiradas y conversacion de mesa.
- Conserva la informacion importante del screenplay y de las notas.
- Si falta informacion, no la rellenes con hechos nuevos.

Prioridad de notas editoriales:
- Las notas bajo "Eliminar" son prohibiciones estrictas.
- No incluyas, no resumas y no sustituyas el material marcado para eliminar.
- Si una nota de "Eliminar" contradice el screenplay base, gana siempre la nota.
- Las notas bajo "Mantener" son material que debe sobrevivir en forma cinematografica.
- Las notas bajo "Planos sugeridos" son guia visual, no una lista que debas copiar.
- La "Intencion" define tono, ritmo y efecto emocional.

Contrato de salida:
- Empieza exactamente con un encabezado de escena, por ejemplo: "# ESCENA 001".
- Despues usa un slugline limpio, por ejemplo: "## INT. CAFETERIA - TARDE".
- No copies cabeceras tecnicas del pipeline como "DESCRIPTION", "DIALOGUE", "PLAYER_INTENT", "PLAYER QUESTION", "REVIEW_REQUIRED" o "MIXED_ENTRIES".
- No escribas placeholders como "(Eliminado segun notas editoriales)".
- No menciones que algo fue eliminado.
- No incluyas notas al final del draft.
- No escribas titulos como "Revision", "Optimizacion", "Objetivo" o similares.
- No expliques lo que vas a hacer.
- No incluyas analisis, comentarios editoriales ni justificacion.
- No uses frases como "A continuacion", "Presento una version" o "El guion actual".
- No uses separadores decorativos como "---".
- No dividas la respuesta en propuesta, revision o recomendaciones.
- El output debe ser utilizable como borrador final de screenplay, no como informe.

Formato esperado:
# ESCENA 001

## INT./EXT. LOCALIZACION - MOMENTO DEL DIA

Texto cinematografico en presente, visual, con accion y atmosfera.
"""


def scene_heading(source: SceneSource) -> str:
    """Return the expected markdown heading for a scene."""

    return source.scene_id.replace("_", " ").upper()


def build_initial_prompt(source: SceneSource) -> str:
    """Build the first-generation prompt for a scene."""

    return f"""{BASE_SYSTEM_INSTRUCTIONS}

# TAREA
Genera un primer borrador cinematografico final para la escena `{source.scene_id}`.
Devuelve una version completa de la escena, no una explicacion de cambios.
La primera linea debe ser "# {scene_heading(source)}".

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
Devuelve una nueva version completa de la escena, no una explicacion de cambios.
La primera linea debe ser "# {scene_heading(source)}".

# SCREENPLAY BASE ORIGINAL
{source.screenplay_markdown}

# NOTAS EDITORIALES
{source.editorial_notes_markdown or "_Sin notas editoriales._"}

# BORRADOR ANTERIOR
{previous_draft}

# AJUSTE DEL DIRECTOR
{user_feedback or "_Sin ajuste adicional._"}
"""
