from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.entities import ConversationStatus, MessageDirection, SenderType, User
from app.routers.auth import get_current_user
from app.schemas.conversation import (
    AgentMessageCreate,
    ConversationActionResponse,
    ConversationListItem,
    ConversationRead,
    MessageRead,
    WhatsAppProvidersStatus,
)
from app.services.conversation import (
    create_message,
    get_conversation_messages,
    get_conversation_with_relations,
    list_conversations,
    update_conversation_tags,
)
from app.services.events import publish_event
from app.services.handling import handling_mode_from_tags
from app.services.outbound import send_conversation_reply
from app.whatsapp.conversation_provider import get_conversation_provider, normalize_provider
from app.whatsapp.factory import list_provider_status

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _handling_mode(conversation) -> str:
    return handling_mode_from_tags(tag.name for tag in conversation.tags)


def _list_item(conversation) -> ConversationListItem:
    item = ConversationListItem.model_validate(conversation)
    item.whatsapp_provider = get_conversation_provider(conversation)
    item.handling_mode = _handling_mode(conversation)  # type: ignore[assignment]
    return item


def _read(conversation) -> ConversationRead:
    data = ConversationRead.model_validate(conversation)
    data.handling_mode = _handling_mode(conversation)  # type: ignore[assignment]
    return data


@router.get("/whatsapp-providers", response_model=WhatsAppProvidersStatus)
async def whatsapp_providers_status() -> WhatsAppProvidersStatus:
    return WhatsAppProvidersStatus(
        default_provider=normalize_provider(settings.whatsapp_default_provider),
        providers=list_provider_status(),
    )


@router.get("", response_model=list[ConversationListItem])
async def get_conversations(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
) -> list[ConversationListItem]:
    conversations = await list_conversations(db, limit=limit)
    return [_list_item(item) for item in conversations]


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    conversation = await get_conversation_with_relations(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _read(conversation)

@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def get_messages(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[MessageRead]:
    conversation = await get_conversation_with_relations(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = await get_conversation_messages(db, conversation_id)
    return [MessageRead.model_validate(message) for message in messages]


@router.post("/{conversation_id}/messages", response_model=ConversationActionResponse)
async def send_agent_message(
    conversation_id: UUID,
    body: AgentMessageCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ConversationActionResponse:
    """Envía un mensaje como agente humano. Opcionalmente lo entrega por el canal."""
    conversation = await get_conversation_with_relations(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.status == ConversationStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Conversation is resolved")

    tag_names = {tag.name for tag in conversation.tags}
    if "bot-apagado" not in tag_names:
        raise HTTPException(
            status_code=409,
            detail="Take the conversation first (bot must be off)",
        )

    try:
        conversation, message = await send_conversation_reply(
            db,
            conversation_id,
            content=body.content.strip(),
            sender_type=SenderType.AGENT,
            send_whatsapp=body.send_whatsapp,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    background_tasks.add_task(
        publish_event,
        "conversation.message.created",
        {
            "conversation": {
                "id": str(conversation.id),
                "status": conversation.status.value,
                "channel": conversation.channel.value,
                "tags": [tag.name for tag in conversation.tags],
                "handling_mode": _handling_mode(conversation),
            },
            "contact": {
                "id": str(conversation.contact.id),
                "phone": conversation.contact.phone,
                "name": conversation.contact.name,
            },
            "message": {
                "id": str(message.id),
                "content": message.content,
                "direction": message.direction.value,
                "sender_type": message.sender_type.value,
            },
            "case": None,
        },
    )

    return ConversationActionResponse(
        conversation=_read(conversation),
        message=MessageRead.model_validate(message),
    )


@router.post("/{conversation_id}/take", response_model=ConversationActionResponse)
async def take_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationActionResponse:
    """Toma la conversación: atención humana; motores externos deben pausar."""
    conversation = await get_conversation_with_relations(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.status == ConversationStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Conversation is resolved")

    operator = current_user.name or current_user.email
    meta = dict(conversation.metadata_ or {})
    meta["takeover"] = {
        "mode": "human",
        "by_user_id": str(current_user.id),
        "by_name": operator,
        "by_email": current_user.email,
    }
    conversation.metadata_ = meta

    conversation = await update_conversation_tags(
        db,
        conversation,
        add=["bot-apagado"],
        remove=["bot-activo"],
    )
    conversation.status = ConversationStatus.PENDING_HUMAN

    system_message = await create_message(
        db,
        conversation,
        direction=MessageDirection.OUTBOUND,
        sender_type=SenderType.SYSTEM,
        content=f"{operator} tomó la conversación. Atención humana (bot externo pausado).",
        payload={
            "audit": "takeover",
            "action": "take",
            "by_user_id": str(current_user.id),
            "by_name": operator,
        },
    )

    conversation = await get_conversation_with_relations(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationActionResponse(
        conversation=_read(conversation),
        message=MessageRead.model_validate(system_message) if system_message else None,
    )


@router.post("/{conversation_id}/release-bot", response_model=ConversationActionResponse)
async def release_bot(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationActionResponse:
    """Libera la conversación: vuelve atención automática."""
    conversation = await get_conversation_with_relations(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation.status == ConversationStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="Conversation is resolved")

    operator = current_user.name or current_user.email
    meta = dict(conversation.metadata_ or {})
    meta["takeover"] = {
        "mode": "automatic",
        "released_by_user_id": str(current_user.id),
        "released_by_name": operator,
        "released_by_email": current_user.email,
    }
    conversation.metadata_ = meta

    conversation = await update_conversation_tags(
        db,
        conversation,
        add=["bot-activo"],
        remove=["bot-apagado"],
    )
    conversation.status = ConversationStatus.OPEN

    system_message = await create_message(
        db,
        conversation,
        direction=MessageDirection.OUTBOUND,
        sender_type=SenderType.SYSTEM,
        content=f"{operator} liberó la conversación. Atención automática reactivada.",
        payload={
            "audit": "takeover",
            "action": "release",
            "by_user_id": str(current_user.id),
            "by_name": operator,
        },
    )

    conversation = await get_conversation_with_relations(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationActionResponse(
        conversation=_read(conversation),
        message=MessageRead.model_validate(system_message) if system_message else None,
    )


@router.post("/{conversation_id}/resolve", response_model=ConversationActionResponse)
async def resolve_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ConversationActionResponse:
    """Marca la conversación como resuelta."""
    conversation = await get_conversation_with_relations(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.status = ConversationStatus.RESOLVED
    await db.flush()

    conversation = await get_conversation_with_relations(db, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationActionResponse(
        conversation=_read(conversation),
        message=None,
    )
