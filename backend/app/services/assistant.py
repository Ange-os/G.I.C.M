from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.agent import run_agent_turn
from app.assistant.proposals import list_proposals_for_messages
from app.models.domain import ActionProposal
from app.models.entities import AssistantMessage, AssistantRole, AssistantThread, Message, User
from app.services.conversation import list_conversations

CONTEXT_CONVERSATIONS = 20
CONTEXT_MESSAGES = 6
CONTEXT_CHAR_LIMIT = 14000
HISTORY_MESSAGES = 16
DEFAULT_TITLE = "Nueva conversación"

STATUS_LABELS = {
    "open": "abierta",
    "pending_human": "esperando que la tome alguien del equipo",
    "resolved": "ya cerrada",
}

SENDER_LABELS = {
    "contact": "La persona",
    "bot": "El bot",
    "agent": "Alguien del equipo",
    "system": "Nota interna",
}

CHANNEL_LABELS = {
    "whatsapp": "WhatsApp",
    "web": "la web",
    "instagram": "Instagram",
}


async def list_threads(db: AsyncSession, user: User) -> list[AssistantThread]:
    stmt = (
        select(AssistantThread)
        .where(AssistantThread.user_id == user.id)
        .order_by(AssistantThread.updated_at.desc())
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def create_thread(db: AsyncSession, user: User) -> AssistantThread:
    thread = AssistantThread(user_id=user.id, title=DEFAULT_TITLE)
    db.add(thread)
    await db.flush()
    return thread


async def get_thread(db: AsyncSession, user: User, thread_id: UUID) -> AssistantThread | None:
    stmt = select(AssistantThread).where(
        AssistantThread.id == thread_id,
        AssistantThread.user_id == user.id,
    )
    return await db.scalar(stmt)


async def list_messages(db: AsyncSession, thread_id: UUID) -> list[AssistantMessage]:
    stmt = (
        select(AssistantMessage)
        .where(AssistantMessage.thread_id == thread_id)
        .order_by(AssistantMessage.created_at.asc())
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def messages_with_actions(
    db: AsyncSession,
    thread_id: UUID,
) -> tuple[list[AssistantMessage], dict[UUID, ActionProposal]]:
    messages = await list_messages(db, thread_id)
    proposals = await list_proposals_for_messages(db, [m.id for m in messages])
    return messages, proposals


async def build_inbox_context(db: AsyncSession) -> str:
    conversations = await list_conversations(db, limit=CONTEXT_CONVERSATIONS)
    if not conversations:
        return "No hay conversaciones cargadas en el inbox."

    ids = [conversation.id for conversation in conversations]
    stmt = select(Message).where(Message.conversation_id.in_(ids)).order_by(Message.created_at.asc())
    stored = list((await db.scalars(stmt)).all())
    by_conversation: dict[UUID, list[Message]] = defaultdict(list)
    for message in stored:
        by_conversation[message.conversation_id].append(message)

    lines: list[str] = []
    latest_line = ""
    latest_at = None
    for conversation in conversations:
        contact = conversation.contact
        phone = contact.phone if contact else "sin teléfono"
        name = contact.name if contact and contact.name else None
        who = f"{name} ({phone})" if name else phone
        channel = CHANNEL_LABELS.get(conversation.channel.value, conversation.channel.value)
        status = STATUS_LABELS.get(conversation.status.value, conversation.status.value)
        attended_by = _attended_by(conversation)
        lines.append(f"Conversación con {who}, por {channel}. Está {status}. {attended_by}")
        for message in by_conversation.get(conversation.id, [])[-CONTEXT_MESSAGES:]:
            text = " ".join((message.content or "").split())
            if not text:
                continue
            if len(text) > 300:
                text = text[:300] + "…"
            speaker = SENDER_LABELS.get(message.sender_type.value, "Alguien")
            when = message.created_at.strftime("%d/%m %H:%M")
            lines.append(f"- {when} — {speaker}: {text}")
            if message.sender_type.value == "system":
                continue
            if latest_at is None or message.created_at >= latest_at:
                latest_at = message.created_at
                latest_line = (
                    f"El último mensaje de una persona o del equipo es del {when}. "
                    f"{speaker} dijo: «{text}». Fue en la conversación con {who}."
                )

    if latest_line:
        lines.insert(0, latest_line)
    context = "\n".join(lines)
    if len(context) > CONTEXT_CHAR_LIMIT:
        context = context[:CONTEXT_CHAR_LIMIT] + "\n…(hay más conversaciones que no entran acá)"
    return context


def _attended_by(conversation) -> str:
    tag_names = {tag.name for tag in conversation.tags}
    if "bot-apagado" in tag_names:
        return "La está atendiendo una persona del equipo."
    if "bot-activo" in tag_names:
        return "La está atendiendo el bot."
    return ""


async def send_message(
    db: AsyncSession,
    user: User,
    thread_id: UUID,
    content: str,
) -> tuple[AssistantThread, list[AssistantMessage], ActionProposal | None]:
    thread = await get_thread(db, user, thread_id)
    if not thread:
        raise LookupError("Conversación del asistente no encontrada")

    text = content.strip()
    db.add(
        AssistantMessage(
            thread_id=thread.id,
            role=AssistantRole.USER,
            content=text,
        )
    )
    if thread.title == DEFAULT_TITLE:
        thread.title = text.split("\n", 1)[0][:80]
    await db.flush()

    history_rows = await list_messages(db, thread.id)
    history: list[dict[str, str]] = []
    for message in history_rows[-HISTORY_MESSAGES:]:
        history.append({"role": message.role.value, "content": message.content})

    reply, proposal = await run_agent_turn(db, user, thread.id, history)

    assistant_message = AssistantMessage(
        thread_id=thread.id,
        role=AssistantRole.ASSISTANT,
        content=reply,
    )
    db.add(assistant_message)
    await db.flush()

    if proposal:
        proposal.message_id = assistant_message.id
        await db.flush()

    thread.updated_at = datetime.now(timezone.utc)
    await db.flush()
    messages = await list_messages(db, thread.id)
    return thread, messages, proposal
