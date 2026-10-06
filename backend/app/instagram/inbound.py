"""Inbound Instagram normalizado desde n8n."""

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
    get_or_create_instagram_contact,
)


@dataclass
class InstagramInboundResult:
    conversation: Conversation
    message: Message | None
    contact_id: UUID
    duplicate: bool


async def persist_instagram_inbound(
    db: AsyncSession,
    *,
    sender_id: str,
    recipient_id: str | None,
    text: str | None,
    external_id: str | None,
    contact_name: str | None = None,
    raw: dict | None = None,
) -> InstagramInboundResult:
    if not sender_id.strip():
        raise ValueError("sender_id requerido")

    content = (text or "").strip()
    if not content:
        raise ValueError("text vacío")

    contact = await get_or_create_instagram_contact(db, sender_id, name=contact_name)
    conversation = await get_open_conversation(db, contact.id, channel=Channel.INSTAGRAM)
    if not conversation:
        conversation = await create_conversation(
            db,
            contact_id=contact.id,
            channel=Channel.INSTAGRAM,
            metadata={
                "provider": "meta",
                "instagram_sender_id": sender_id.strip(),
                "instagram_account_id": (recipient_id or "").strip() or None,
            },
        )
    else:
        meta = dict(conversation.metadata_ or {})
        meta["instagram_sender_id"] = sender_id.strip()
        if recipient_id:
            meta["instagram_account_id"] = recipient_id.strip()
        conversation.metadata_ = meta

    message = await create_message(
        db,
        conversation,
        direction=MessageDirection.INBOUND,
        sender_type=SenderType.CONTACT,
        content=content,
        payload={
            "provider": "meta",
            "channel": "instagram",
            "sender_id": sender_id.strip(),
            "recipient_id": recipient_id,
            "raw": raw or {},
        },
        external_id=external_id,
    )

    loaded = await get_conversation_with_relations(db, conversation.id)
    if loaded is None:
        raise RuntimeError("Conversation not found after Instagram inbound")

    return InstagramInboundResult(
        conversation=loaded,
        message=message,
        contact_id=contact.id,
        duplicate=message is None,
    )
