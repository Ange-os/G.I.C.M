from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.entities import Channel, MessageDirection, SenderType
from app.schemas.conversation import ConversationRead, MessageRead, N8nInboundRequest, N8nInboundResponse
from app.services.conversation import (
    create_message,
    get_conversation_with_relations,
    update_conversation_tags,
)
from app.services.events import publish_event
from app.services.handling import handling_mode_from_tags, is_human_handling
from app.whatsapp.base import WhatsAppProviderError
from app.whatsapp.conversation_provider import get_conversation_provider
from app.whatsapp.factory import get_whatsapp_provider

router = APIRouter(prefix="/webhooks/n8n", tags=["webhooks-n8n"])


def _verify_n8n_key(x_n8n_api_key: str | None) -> None:
    if settings.n8n_api_key and x_n8n_api_key != settings.n8n_api_key:
        raise HTTPException(status_code=401, detail="Invalid n8n API key")


@router.post("/inbound", response_model=N8nInboundResponse)
async def n8n_inbound(
    body: N8nInboundRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_n8n_api_key: str | None = Header(default=None, alias="X-N8N-API-Key"),
) -> N8nInboundResponse:
    """
    Endpoint para que n8n envíe mensajes, actualice tags (ej. bot-apagado)
    y cambie el estado de la conversación.
    Con send_whatsapp=true la API envía el mensaje por el provider de la conversación
    (ycloud o meta), salvo si la conversación está en atención humana.
    """
    _verify_n8n_key(x_n8n_api_key)

    conversation = await get_conversation_with_relations(db, body.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    created_message = None

    if body.tags:
        conversation = await update_conversation_tags(
            db,
            conversation,
            add=body.tags.add,
            remove=body.tags.remove,
        )

    if body.status:
        conversation.status = body.status

    tag_names = {tag.name for tag in conversation.tags}
    human_mode = is_human_handling(tag_names)
    # Tras takeover, el bot de n8n no puede entregar al canal (anti doble respuesta).
    block_bot_delivery = human_mode and body.message and body.message.sender_type == SenderType.BOT

    if body.message:
        message_payload = dict(body.message.payload)
        external_id = None
        deliver = (
            body.send_whatsapp
            and conversation.channel == Channel.WHATSAPP
            and body.message.content
            and not block_bot_delivery
        )

        if block_bot_delivery and body.send_whatsapp:
            message_payload["delivery_skipped"] = "human_handling"
            message_payload["handling_mode"] = "human"

        if deliver:
            provider_name = get_conversation_provider(conversation)
            provider = get_whatsapp_provider(provider_name)
            phone_number_id = (conversation.metadata_ or {}).get("phone_number_id")
            if not phone_number_id and conversation.ycloud_phone_number_id:
                phone_number_id = conversation.ycloud_phone_number_id
            try:
                result = await provider.send_text(
                    to=conversation.contact.phone,
                    text=body.message.content,
                    phone_number_id=str(phone_number_id) if phone_number_id else None,
                )
                message_payload["provider"] = provider_name
                message_payload[provider_name] = result.raw
                external_id = result.external_id
            except WhatsAppProviderError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        # Si el bot intenta responder con takeover activo, no persistir ese spam en el hilo.
        if block_bot_delivery:
            created_message = None
        else:
            created_message = await create_message(
                db,
                conversation,
                direction=MessageDirection.OUTBOUND,
                sender_type=body.message.sender_type,
                content=body.message.content,
                media_url=body.message.media_url,
                payload=message_payload,
                external_id=external_id,
            )

    conversation = await get_conversation_with_relations(db, body.conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    event_name = "conversation.updated"
    if created_message:
        event_name = "conversation.message.created"

    background_tasks.add_task(
        publish_event,
        event_name,
        {
            "conversation": {
                "id": str(conversation.id),
                "status": conversation.status.value,
                "channel": conversation.channel.value,
                "tags": [tag.name for tag in conversation.tags],
                "handling_mode": handling_mode_from_tags(tag.name for tag in conversation.tags),
                "whatsapp_provider": get_conversation_provider(conversation),
            },
            "contact": {
                "id": str(conversation.contact.id),
                "phone": conversation.contact.phone,
                "name": conversation.contact.name,
            },
            "message": (
                {
                    "id": str(created_message.id),
                    "content": created_message.content,
                    "direction": created_message.direction.value,
                    "sender_type": created_message.sender_type.value,
                }
                if created_message
                else None
            ),
            "case": None,
        },
    )

    read = ConversationRead.model_validate(conversation)
    read.handling_mode = handling_mode_from_tags(tag.name for tag in conversation.tags)  # type: ignore[assignment]
    return N8nInboundResponse(
        conversation=read,
        message=MessageRead.model_validate(created_message) if created_message else None,
    )
