"""Pipeline compartido de inbound WhatsApp (YCloud / Meta)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Conversation, Message
from app.services.conversation import (
    create_conversation,
    create_message,
    get_conversation_with_relations,
    get_open_conversation,
    get_or_create_contact,
)
from app.whatsapp.base import NormalizedInbound
from app.whatsapp.conversation_provider import set_conversation_provider


@dataclass
class InboundResult:
    conversation: Conversation
    message: Message | None
    contact_id: UUID
    duplicate: bool


async def persist_inbound(
    db: AsyncSession,
    event: NormalizedInbound,
) -> InboundResult:
    contact = await get_or_create_contact(
        db,
        phone=event.from_phone,
        name=event.contact_name,
    )
    conversation = await get_open_conversation(
        db,
        contact.id,
        channel=event.channel,
        whatsapp_provider=event.provider,
    )
    if not conversation:
        conversation = await create_conversation(
            db,
            contact_id=contact.id,
            channel=event.channel,
            ycloud_phone_number_id=event.phone_number_id if event.provider == "ycloud" else None,
            whatsapp_provider=event.provider,
            phone_number_id=event.phone_number_id,
        )
    else:
        set_conversation_provider(conversation, event.provider)
        meta = dict(conversation.metadata_ or {})
        if event.phone_number_id:
            meta["phone_number_id"] = event.phone_number_id
        conversation.metadata_ = meta
        if event.provider == "ycloud" and event.phone_number_id:
            conversation.ycloud_phone_number_id = event.phone_number_id

    message = await create_message(
        db,
        conversation,
        direction=event.direction,
        sender_type=event.sender_type,
        content=event.content,
        media_url=event.media_url,
        payload={
            "provider": event.provider,
            "media_type": event.media_type,
            "raw": event.raw,
        },
        external_id=event.external_id,
    )

    conversation = await get_conversation_with_relations(db, conversation.id)
    if conversation is None:
        raise RuntimeError("Conversation not found after inbound save")

    return InboundResult(
        conversation=conversation,
        message=message,
        contact_id=contact.id,
        duplicate=message is None,
    )
