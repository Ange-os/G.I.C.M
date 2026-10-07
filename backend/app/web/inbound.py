"""Inbound canal web (xIA.ar) espejado al Inbox."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Channel, Conversation, Message, MessageDirection, SenderType
from app.services.conversation import (
    create_conversation,
    create_message,
    get_conversation_with_relations,
    get_open_conversation,
    get_or_create_web_contact,
)


@dataclass
class WebInboundResult:
    conversation: Conversation
    message: Message | None
    contact_id: UUID
    duplicate: bool


def _map_role(role: str | None) -> tuple[MessageDirection, SenderType]:
    normalized = (role or "contact").strip().lower()
    if normalized == "bot":
        return MessageDirection.OUTBOUND, SenderType.BOT
    if normalized == "agent":
        return MessageDirection.OUTBOUND, SenderType.AGENT
    return MessageDirection.INBOUND, SenderType.CONTACT


async def persist_web_inbound(
    db: AsyncSession,
    *,
    sender_id: str,
    text: str | None,
    external_id: str | None,
    role: str | None = "contact",
    email: str | None = None,
    name: str | None = None,
    picture: str | None = None,
    external_conversation_id: str | None = None,
    source: str | None = None,
    raw: dict | None = None,
) -> WebInboundResult:
    if not sender_id.strip():
        raise ValueError("senderId requerido")

    content = (text or "").strip()
    if not content:
        raise ValueError("text vacío")

    contact = await get_or_create_web_contact(
        db,
        sender_id,
        name=name,
        email=email,
        picture=picture,
    )
    conversation = await get_open_conversation(db, contact.id, channel=Channel.WEB)
    meta_base = {
        "provider": "xia",
        "channel": "web",
        "xia_sender_id": sender_id.strip(),
        "source": source or "xia.ar",
    }
    if email:
        meta_base["email"] = email.strip()
    if external_conversation_id:
        meta_base["xia_conversation_id"] = external_conversation_id.strip()

    if not conversation:
        conversation = await create_conversation(
            db,
            contact_id=contact.id,
            channel=Channel.WEB,
            metadata=meta_base,
        )
    else:
        meta = dict(conversation.metadata_ or {})
        meta.update(meta_base)
        conversation.metadata_ = meta

    direction, sender_type = _map_role(role)
    message = await create_message(
        db,
        conversation,
        direction=direction,
        sender_type=sender_type,
        content=content,
        payload={
            "provider": "xia",
            "channel": "web",
            "role": role,
            "raw": raw or {},
        },
        external_id=external_id,
    )

    loaded = await get_conversation_with_relations(db, conversation.id)
    if loaded is None:
        raise RuntimeError("Conversation not found after web inbound")

    return WebInboundResult(
        conversation=loaded,
        message=message,
        contact_id=contact.id,
        duplicate=message is None,
    )
