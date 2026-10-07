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


def _map_page_outbound_role(role: str | None) -> SenderType:
    normalized = (role or "bot").strip().lower()
    if normalized == "agent":
        return SenderType.AGENT
    return SenderType.BOT


async def persist_instagram_inbound(
    db: AsyncSession,
    *,
    sender_id: str,
    recipient_id: str | None,
    text: str | None,
    external_id: str | None,
    contact_name: str | None = None,
    raw: dict | None = None,
    page_outbound: bool = False,
    role: str | None = None,
) -> InstagramInboundResult:
    """
    Mensaje del usuario: sender_id = IGSID del contacto.
    Respuesta de la página/Agent (echo): recipient_id = IGSID del contacto,
    sender_id = ID de la página.
    """
    content = (text or "").strip()
    if not content:
        raise ValueError("text vacío")

    if page_outbound:
        user_igsid = (recipient_id or "").strip()
        page_id = sender_id.strip()
        if not user_igsid:
            raise ValueError("recipientId requerido para respuestas del bot/página (echo)")
        if not page_id:
            raise ValueError("senderId de la página vacío")
        contact_igsid = user_igsid
        direction = MessageDirection.OUTBOUND
        sender_type = _map_page_outbound_role(role)
    else:
        contact_igsid = sender_id.strip()
        if not contact_igsid:
            raise ValueError("sender_id requerido")
        page_id = (recipient_id or "").strip() or None
        direction = MessageDirection.INBOUND
        sender_type = SenderType.CONTACT

    contact = await get_or_create_instagram_contact(db, contact_igsid, name=contact_name)
    conversation = await get_open_conversation(db, contact.id, channel=Channel.INSTAGRAM)

    meta_base = {
        "provider": "meta",
        "instagram_sender_id": contact_igsid,
        "instagram_account_id": page_id,
    }

    if not conversation:
        conversation = await create_conversation(
            db,
            contact_id=contact.id,
            channel=Channel.INSTAGRAM,
            metadata=meta_base,
        )
    else:
        meta = dict(conversation.metadata_ or {})
        # No pisar el IGSID del usuario con el ID de la página en ecos.
        meta["instagram_sender_id"] = contact_igsid
        if page_id:
            meta["instagram_account_id"] = page_id
        conversation.metadata_ = meta

    message = await create_message(
        db,
        conversation,
        direction=direction,
        sender_type=sender_type,
        content=content,
        payload={
            "provider": "meta",
            "channel": "instagram",
            "page_outbound": page_outbound,
            "role": role or ("bot" if page_outbound else "contact"),
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
