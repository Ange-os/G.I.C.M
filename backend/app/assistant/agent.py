"""Motor del agente: intención → tools → texto o ActionProposal."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.tools.base import ToolContext
from app.assistant.tools.registry import get_tool, openai_tools_for_user
from app.domain.factory import get_domain_repository
from app.models.domain import ActionProposal, ActionProposalStatus
from app.models.entities import User
from app.services.deepseek import ChatCompletionResult, complete_chat_with_tools

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = """\
Sos el agente operativo del círculo médico (Conversa Platform).
Hablás en español rioplatense, claro y breve.

Tenés tools para consultar datos de negocio (obras sociales, convenios, médicos)
y conversaciones del inbox. También podés preparar acciones (mail, suspender/activar convenio).

Reglas:
- Para datos de obras sociales, convenios o médicos: usá siempre las tools. No inventes.
- Las tools prepare_* NO ejecutan nada: crean una propuesta. Después explicá en 1-2 frases
  que el usuario debe revisar y confirmar la tarjeta.
- Si hay ambigüedad (varios convenios u organizaciones), preguntá antes de preparar la acción.
- Si el usuario arranca una intención sin todos los datos (por ejemplo desde el menú Acciones),
  pedí lo que falte en preguntas cortas, de a una o dos, y no prepares la acción hasta tener
  lo mínimo. No inventes destinatarios ni especialidades.
- No digas que ya enviaste un mail o que ya suspendiste un convenio hasta que el usuario confirme.
- No menciones ids técnicos salvo que el usuario los pida.
- No envíes WhatsApp ni modifiques el inbox desde acá.
- Si te preguntan algo del inbox, usá search_conversation.
"""


async def run_agent_turn(
    db: AsyncSession,
    user: User,
    thread_id: UUID,
    history: list[dict[str, str]],
) -> tuple[str, ActionProposal | None]:
    """Ejecuta el loop del agente. Devuelve (texto_respuesta, propuesta_opcional)."""

    tools = openai_tools_for_user(user)
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    domain = get_domain_repository(db)
    ctx = ToolContext(db=db, user=user, domain=domain, thread_id=thread_id)
    pending_proposal: ActionProposal | None = None

    for _ in range(MAX_TOOL_ROUNDS):
        result: ChatCompletionResult = await complete_chat_with_tools(
            messages,
            tools=tools or None,
        )

        if not result.tool_calls:
            text = (result.content or "").strip()
            if pending_proposal and not text:
                text = (
                    "Dejé preparada la acción acá abajo. Revisala y confirmá si querés seguir."
                )
            return text or "Listo.", pending_proposal

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": result.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in result.tool_calls
            ],
        }
        messages.append(assistant_msg)

        for call in result.tool_calls:
            tool = get_tool(call.name)
            if not tool:
                tool_output = json.dumps({"error": f"Tool desconocida: {call.name}"})
            else:
                try:
                    args = json.loads(call.arguments or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except json.JSONDecodeError:
                    args = {}
                try:
                    tool_output = await tool.handler(ctx, **args)
                except TypeError as exc:
                    tool_output = json.dumps({"error": f"Argumentos inválidos: {exc}"})
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Tool %s falló", call.name)
                    tool_output = json.dumps({"error": str(exc)}, ensure_ascii=False)

            pending_proposal = await _extract_proposal(db, tool_output) or pending_proposal
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": tool_output,
                }
            )

        if pending_proposal:
            # Una acción preparada: pedimos cierre en texto sin más tools.
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Ya hay una propuesta de acción creada. "
                        "Respondé solo con un mensaje corto al usuario, sin llamar más tools."
                    ),
                }
            )
            closing = await complete_chat_with_tools(messages, tools=None)
            text = (closing.content or "").strip()
            if not text:
                text = (
                    "Dejé preparada la acción acá abajo. Revisala y confirmá si querés seguir."
                )
            return text, pending_proposal

    return (
        "Necesité demasiados pasos para resolverlo. Probá reformular la pregunta.",
        pending_proposal,
    )


async def _extract_proposal(db: AsyncSession, tool_output: str) -> ActionProposal | None:
    try:
        data = json.loads(tool_output)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    proposal_id = data.get("action_proposal_id")
    if not proposal_id:
        return None
    try:
        uid = UUID(str(proposal_id))
    except ValueError:
        return None
    proposal = await db.get(ActionProposal, uid)
    if proposal and proposal.status == ActionProposalStatus.AWAITING_CONFIRMATION:
        return proposal
    return None
