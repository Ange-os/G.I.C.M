from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import (
    Channel,
    Contact,
    Conversation,
    ConversationStatus,
    Message,
    MessageDirection,
    SenderType,
    Tag,
)


DEFAULT_TAGS = [
    ("bot-activo", "El bot puede responder automáticamente"),
    ("bot-apagado", "El bot está desactivado; atención humana"),
]


async def seed_default_tags(db: AsyncSession) -> None:
    for name, description in DEFAULT_TAGS:
        existing = await db.scalar(select(Tag).where(Tag.name == name))
        if not existing:
            db.add(Tag(name=name, description=description))


async def get_or_create_contact(db: AsyncSession, phone: str, name: str | None = None) -> Contact:
    contact = await db.scalar(select(Contact).where(Contact.phone == phone))
    if contact:
        if name and not contact.name:
            contact.name = name
        return contact

    contact = Contact(phone=phone, name=name)
    db.add(contact)
    await db.flush()
    return contact


def instagram_contact_key(sender_id: str) -> str:
    """Clave estable en Contact.phone para un usuario de Instagram (IGSID)."""
    key = f"ig:{sender_id.strip()}"
    if len(key) <= 32:
        return key
    import hashlib

    return "ig:" + hashlib.sha1(sender_id.encode("utf-8")).hexdigest()[:29]


def _instagram_placeholder_name(name: str | None) -> bool:
    if not name or not name.strip():
        return True
    return name.strip().startswith("IG ")


async def get_or_create_instagram_contact(
    db: AsyncSession,
    sender_id: str,
    name: str | None = None,
    *,
    username: str | None = None,
    picture: str | None = None,
) -> Contact:
    sender_id = sender_id.strip()
    if not sender_id:
        raise ValueError("sender_id de Instagram vacío")

    display = (name or "").strip() or None
    handle = (username or "").strip().lstrip("@") or None
    pic = (picture or "").strip() or None
    if not display and handle:
        display = handle

    key = instagram_contact_key(sender_id)
    contact = await db.scalar(select(Contact).where(Contact.phone == key))
    if contact:
        meta = dict(contact.metadata_ or {})
        meta["instagram_sender_id"] = sender_id
        meta["channel"] = "instagram"
        if handle:
            meta["instagram_username"] = handle
        if pic:
            meta["picture"] = pic
        contact.metadata_ = meta
        if display and (
            _instagram_placeholder_name(contact.name)
            or (handle and contact.name == handle and display != handle)
        ):
            contact.name = display
        return contact

    meta = {"instagram_sender_id": sender_id, "channel": "instagram"}
    if handle:
        meta["instagram_username"] = handle
    if pic:
        meta["picture"] = pic

    contact = Contact(
        phone=key,
        name=display or (handle or f"IG {sender_id[-6:]}"),
        metadata_=meta,
    )
    db.add(contact)
    await db.flush()
    return contact


def web_contact_key(sender_id: str) -> str:
    """Clave estable en Contact.phone para un usuario web (Google sub / xIA)."""
    key = f"web:{sender_id.strip()}"
    if len(key) <= 32:
        return key
    import hashlib

    return "web:" + hashlib.sha1(sender_id.encode("utf-8")).hexdigest()[:28]


async def get_or_create_web_contact(
    db: AsyncSession,
    sender_id: str,
    *,
    name: str | None = None,
    email: str | None = None,
    picture: str | None = None,
) -> Contact:
    sender_id = sender_id.strip()
    if not sender_id:
        raise ValueError("sender_id web vacío")

    key = web_contact_key(sender_id)
    contact = await db.scalar(select(Contact).where(Contact.phone == key))
    meta_update = {
        "xia_sender_id": sender_id,
        "channel": "web",
        "provider": "xia",
    }
    if email:
        meta_update["email"] = email.strip()
    if picture:
        meta_update["picture"] = picture.strip()

    if contact:
        meta = dict(contact.metadata_ or {})
        meta.update(meta_update)
        contact.metadata_ = meta
        if name and (not contact.name or contact.name.startswith("Web ")):
            contact.name = name
        return contact

    contact = Contact(
        phone=key,
        name=name or (email.split("@")[0] if email else f"Web {sender_id[-6:]}"),
        metadata_=meta_update,
    )
    db.add(contact)
    await db.flush()
    return contact


async def get_open_conversation(
    db: AsyncSession,
    contact_id: UUID,
    channel: Channel = Channel.WHATSAPP,
    whatsapp_provider: str | None = None,
) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(
            Conversation.contact_id == contact_id,
            Conversation.channel == channel,
            Conversation.status != ConversationStatus.RESOLVED,
        )
        .options(selectinload(Conversation.contact), selectinload(Conversation.tags))
        .order_by(Conversation.updated_at.desc())
    )
    rows = list((await db.scalars(stmt)).all())
    if not whatsapp_provider:
        return rows[0] if rows else None

    from app.whatsapp.conversation_provider import get_conversation_provider

    for conversation in rows:
        if get_conversation_provider(conversation) == whatsapp_provider:
            return conversation
    return None


async def create_conversation(
    db: AsyncSession,
    contact_id: UUID,
    channel: Channel = Channel.WHATSAPP,
    ycloud_phone_number_id: str | None = None,
    whatsapp_provider: str | None = None,
    phone_number_id: str | None = None,
    metadata: dict | None = None,
) -> Conversation:
    from app.whatsapp.conversation_provider import normalize_provider

    bot_activo = await db.scalar(select(Tag).where(Tag.name == "bot-activo"))
    meta: dict = dict(metadata or {})
    if channel == Channel.WHATSAPP:
        meta.setdefault("whatsapp_provider", normalize_provider(whatsapp_provider))
        if phone_number_id:
            meta["phone_number_id"] = phone_number_id
    elif channel == Channel.INSTAGRAM:
        meta.setdefault("provider", "meta")
        meta.setdefault("channel", "instagram")
    elif channel == Channel.WEB:
        meta.setdefault("provider", "xia")
        meta.setdefault("channel", "web")
    conversation = Conversation(
        contact_id=contact_id,
        channel=channel,
        ycloud_phone_number_id=ycloud_phone_number_id,
        metadata_=meta,
        tags=[bot_activo] if bot_activo else [],
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def get_conversation_with_relations(db: AsyncSession, conversation_id: UUID) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(
            selectinload(Conversation.contact),
            selectinload(Conversation.tags),
            selectinload(Conversation.messages),
        )
    )
    return await db.scalar(stmt)


async def list_conversations(
    db: AsyncSession,
    limit: int = 50,
    *,
    channel: Channel | None = None,
) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.contact), selectinload(Conversation.tags))
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    if channel is not None:
        stmt = stmt.where(Conversation.channel == channel)
    result = await db.scalars(stmt)
    return list(result.all())


async def get_conversation_messages(db: AsyncSession, conversation_id: UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def get_or_create_tag(db: AsyncSession, name: str) -> Tag:
    tag = await db.scalar(select(Tag).where(Tag.name == name))
    if tag:
        return tag
    tag = Tag(name=name)
    db.add(tag)
    await db.flush()
    return tag


async def update_conversation_tags(
    db: AsyncSession,
    conversation: Conversation,
    add: list[str],
    remove: list[str],
) -> Conversation:
    loaded = await db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation.id)
        .options(selectinload(Conversation.tags))
    )
    if not loaded:
        return conversation
    conversation = loaded

    if remove:
        remove_set = set(remove)
        conversation.tags = [tag for tag in conversation.tags if tag.name not in remove_set]

    if add:
        current_names = {tag.name for tag in conversation.tags}
        for tag_name in add:
            if tag_name not in current_names:
                tag = await get_or_create_tag(db, tag_name)
                conversation.tags.append(tag)
                current_names.add(tag_name)

    if "bot-apagado" in add:
        conversation.status = ConversationStatus.PENDING_HUMAN
    elif "bot-activo" in add and conversation.status == ConversationStatus.PENDING_HUMAN:
        conversation.status = ConversationStatus.OPEN

    await db.flush()
    return conversation


async def create_message(
    db: AsyncSession,
    conversation: Conversation,
    *,
    direction: MessageDirection,
    sender_type: SenderType,
    content: str | None = None,
    media_url: str | None = None,
    payload: dict | None = None,
    external_id: str | None = None,
) -> Message | None:
    if external_id:
        existing = await db.scalar(select(Message).where(Message.external_id == external_id))
        if existing:
            return None

    message = Message(
        conversation_id=conversation.id,
        direction=direction,
        sender_type=sender_type,
        content=content,
        media_url=media_url,
        payload=payload or {},
        external_id=external_id,
    )
    db.add(message)
    await db.flush()
    return message
