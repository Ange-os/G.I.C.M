"""Catálogo de acciones del panel: intenciones que arrancan el agente."""

from __future__ import annotations

from dataclasses import dataclass

from app.assistant.permissions import allowed_tool_names
from app.models.entities import User


@dataclass(frozen=True)
class CatalogAction:
    id: str
    title: str
    description: str
    starter_message: str
    category: str  # "action" | "query"
    required_tools: frozenset[str]


_CATALOG: tuple[CatalogAction, ...] = (
    CatalogAction(
        id="send_email",
        title="Enviar mail",
        description="El agente te pide destinatario y mensaje, y prepara el envío.",
        starter_message=(
            "Quiero enviar un mail. Todavía no tengo todos los datos. "
            "Preguntame a quién (obra social o email), el asunto y qué tiene que decir. "
            "Cuando tengas lo mínimo, prepará el mail para que yo lo confirme."
        ),
        category="action",
        required_tools=frozenset({"prepare_email"}),
    ),
    CatalogAction(
        id="suspend_agreement",
        title="Suspender convenio",
        description="El agente identifica obra social y especialidad, y pide confirmación.",
        starter_message=(
            "Quiero suspender un convenio. "
            "Preguntame la obra social y la especialidad. "
            "Si hay más de uno, pedime que elija. "
            "Cuando esté claro, prepará la suspensión para confirmar."
        ),
        category="action",
        required_tools=frozenset({"prepare_suspend_agreement"}),
    ),
    CatalogAction(
        id="activate_agreement",
        title="Activar convenio",
        description="El agente busca un convenio suspendido y propone reactivarlo.",
        starter_message=(
            "Quiero reactivar un convenio. "
            "Preguntame la obra social y la especialidad. "
            "Cuando esté claro, prepará la activación para confirmar."
        ),
        category="action",
        required_tools=frozenset({"prepare_activate_agreement"}),
    ),
    CatalogAction(
        id="search_agreements",
        title="Consultar convenios",
        description="Preguntá por obras sociales, especialidades o estados.",
        starter_message=(
            "Quiero consultar convenios. "
            "Preguntame si busco por obra social, especialidad o estado "
            "(activo/suspendido), y mostrame el resultado."
        ),
        category="query",
        required_tools=frozenset({"search_agreement"}),
    ),
    CatalogAction(
        id="search_doctors",
        title="Buscar médicos",
        description="Buscá por nombre, especialidad o estado de convenio.",
        starter_message=(
            "Quiero buscar médicos. "
            "Preguntame nombre, especialidad o si tienen convenio activo/suspendido, "
            "y mostrame el resultado."
        ),
        category="query",
        required_tools=frozenset({"search_doctors"}),
    ),
    CatalogAction(
        id="search_inbox",
        title="Buscar en el inbox",
        description="Encontrá conversaciones por nombre, teléfono o estado.",
        starter_message=(
            "Quiero buscar una conversación del inbox. "
            "Preguntame nombre, teléfono o estado, y mostrame lo que encuentres."
        ),
        category="query",
        required_tools=frozenset({"search_conversation"}),
    ),
    CatalogAction(
        id="search_organization",
        title="Buscar obra social",
        description="Datos de contacto de OSDE, PAMI y demás organizaciones demo.",
        starter_message=(
            "Quiero buscar una obra social. "
            "Preguntame el nombre y mostrame el contacto que tengas."
        ),
        category="query",
        required_tools=frozenset({"search_organization"}),
    ),
)


def catalog_for_user(user: User) -> list[dict]:
    allowed = allowed_tool_names(user)
    items: list[dict] = []
    for action in _CATALOG:
        if not action.required_tools.issubset(allowed):
            continue
        items.append(
            {
                "id": action.id,
                "title": action.title,
                "description": action.description,
                "starter_message": action.starter_message,
                "category": action.category,
            }
        )
    return items
