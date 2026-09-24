from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AssistantMessage, AssistantRole, AssistantThread, Message, User
from app.services.conversation import list_conversations
from app.services.deepseek import complete_chat

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


def _system_prompt(context: str) -> str:
    return (
        "Sos un compañero de administración de un círculo médico. "
        "Hablás en español rioplatense, con frases cortas, como se lo explicarías a alguien del mostrador. "
        "Respondé la pregunta y nada más. Sin títulos, sin viñetas y sin repetir el formato de los datos. "
        "No menciones códigos, ids, etiquetas ni palabras como recorte, bot-activo, bot-apagado, contact o system. "
        "Si el bot atiende la conversación, decí «la está atendiendo el bot». "
        "Si la tomó el equipo, decí «la tomó alguien del equipo». "
        "Una nota interna no es un mensaje de la persona: si preguntan por el último mensaje, "
        "priorizá lo que escribió la persona, el bot o el equipo, y mencioná la nota interna solo si cambia el sentido. "
        "Si no hay nombre, usá el teléfono. "
        "Si el dato no está en la información de abajo, decilo con naturalidad. "
        "No inventes deudas, expedientes ni datos de socios. "
        "La información de abajo son las conversaciones más recientes, no todo el historial. "
        "No redactes un WhatsApp salvo que te lo pidan.\n\n"
        f"Información del inbox:\n{context}"
    )


async def send_message(
    db: AsyncSession,
    user: User,
    thread_id: UUID,
    content: str,
) -> tuple[AssistantThread, list[AssistantMessage]]:
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

    context = await build_inbox_context(db)
    history = await list_messages(db, thread.id)
    payload: list[dict[str, str]] = [{"role": "system", "content": _system_prompt(context)}]
    for message in history[-HISTORY_MESSAGES:]:
        payload.append({"role": message.role.value, "content": message.content})

    reply = await complete_chat(payload)
    db.add(
        AssistantMessage(
            thread_id=thread.id,
            role=AssistantRole.ASSISTANT,
            content=reply,
        )
    )
    thread.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return thread, await list_messages(db, thread.id)
