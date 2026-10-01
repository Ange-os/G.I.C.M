"""Tools de lectura: consultan Data Views, no modifican nada."""

from __future__ import annotations

import json
from uuid import UUID

from app.assistant.tools.base import ToolContext, ToolSpec
from app.models.domain import AgreementStatus
from app.models.entities import ConversationStatus
from app.services.conversation import list_conversations


def _dump(data: object) -> str:
    if hasattr(data, "model_dump"):
        return json.dumps(data.model_dump(mode="json"), ensure_ascii=False)
    if isinstance(data, list):
        return json.dumps(
            [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in data],
            ensure_ascii=False,
        )
    return json.dumps(data, ensure_ascii=False)


async def _search_organization(ctx: ToolContext, query: str) -> str:
    rows = await ctx.domain.search_organizations(query, limit=8)
    if not rows:
        return json.dumps({"results": [], "message": "No encontré obras sociales con ese nombre."})
    return _dump(rows)


async def _search_agreement(
    ctx: ToolContext,
    organization_query: str | None = None,
    specialty: str | None = None,
    status: str | None = None,
) -> str:
    status_enum = None
    if status:
        try:
            status_enum = AgreementStatus(status.lower())
        except ValueError:
            return json.dumps({"error": "status debe ser active o suspended"})
    rows = await ctx.domain.search_agreements(
        organization_query=organization_query,
        specialty=specialty,
        status=status_enum,
        limit=15,
    )
    if not rows:
        return json.dumps({"results": [], "message": "No encontré convenios con esos filtros."})
    return _dump(rows)


async def _get_agreement_summary(ctx: ToolContext, agreement_id: str) -> str:
    try:
        uid = UUID(agreement_id)
    except ValueError:
        return json.dumps({"error": "agreement_id inválido"})
    row = await ctx.domain.get_agreement(uid)
    if not row:
        return json.dumps({"error": "Convenio no encontrado"})
    return _dump(row)


async def _search_doctors(
    ctx: ToolContext,
    query: str | None = None,
    specialty: str | None = None,
    agreement_status: str | None = None,
) -> str:
    status_enum = None
    if agreement_status:
        try:
            status_enum = AgreementStatus(agreement_status.lower())
        except ValueError:
            return json.dumps({"error": "agreement_status debe ser active o suspended"})
    rows = await ctx.domain.search_doctors(
        query=query,
        specialty=specialty,
        agreement_status=status_enum,
        limit=15,
    )
    if not rows:
        return json.dumps({"results": [], "message": "No encontré médicos con esos filtros."})
    return _dump(rows)


async def _search_conversation(
    ctx: ToolContext,
    query: str | None = None,
    status: str | None = None,
) -> str:
    conversations = await list_conversations(ctx.db, limit=30)
    status_filter = None
    if status:
        try:
            status_filter = ConversationStatus(status)
        except ValueError:
            return json.dumps({"error": "status debe ser open, pending_human o resolved"})

    needle = (query or "").strip().lower()
    results = []
    for conversation in conversations:
        if status_filter and conversation.status != status_filter:
            continue
        contact = conversation.contact
        phone = (contact.phone if contact else "") or ""
        name = (contact.name if contact else "") or ""
        hay = f"{name} {phone}".lower()
        if needle and needle not in hay:
            continue
        results.append(
            {
                "id": str(conversation.id),
                "contact_name": name or None,
                "phone": phone or None,
                "status": conversation.status.value,
                "channel": conversation.channel.value,
                "tags": [tag.name for tag in conversation.tags],
            }
        )
        if len(results) >= 10:
            break

    if not results:
        return json.dumps({"results": [], "message": "No encontré conversaciones."})
    return json.dumps({"results": results}, ensure_ascii=False)


READ_TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="search_organization",
        description="Busca obras sociales / organizaciones por nombre (ej. OSDE, PAMI).",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nombre o parte del nombre"},
            },
            "required": ["query"],
        },
        kind="read",
        handler=_search_organization,
    ),
    ToolSpec(
        name="search_agreement",
        description="Busca convenios por obra social, especialidad y/o estado (active/suspended).",
        parameters={
            "type": "object",
            "properties": {
                "organization_query": {"type": "string"},
                "specialty": {"type": "string"},
                "status": {"type": "string", "enum": ["active", "suspended"]},
            },
        },
        kind="read",
        handler=_search_agreement,
    ),
    ToolSpec(
        name="get_agreement_summary",
        description="Obtiene el detalle de un convenio por su id.",
        parameters={
            "type": "object",
            "properties": {
                "agreement_id": {"type": "string"},
            },
            "required": ["agreement_id"],
        },
        kind="read",
        handler=_get_agreement_summary,
    ),
    ToolSpec(
        name="search_doctors",
        description="Busca médicos por nombre, especialidad o estado del convenio vinculado.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "specialty": {"type": "string"},
                "agreement_status": {"type": "string", "enum": ["active", "suspended"]},
            },
        },
        kind="read",
        handler=_search_doctors,
    ),
    ToolSpec(
        name="search_conversation",
        description="Busca conversaciones del inbox por nombre/teléfono o estado.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "pending_human", "resolved"]},
            },
        },
        kind="read",
        handler=_search_conversation,
    ),
]
