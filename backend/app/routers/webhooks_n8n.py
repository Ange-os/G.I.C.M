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
from app.services.ycloud_outbound import YCloudError, send_whatsapp_text

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
    Con send_whatsapp=true la API envía el mensaje por YCloud al contacto.
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

    if body.message:
        message_payload = dict(body.message.payload)
        ycloud_response = None

        if (
            body.send_whatsapp
            and conversation.channel == Channel.WHATSAPP
            and body.message.content
        ):
            try:
                ycloud_response = await send_whatsapp_text(
                    to=conversation.contact.phone,
                    text=body.message.content,
                )
                message_payload["ycloud"] = ycloud_response
            except YCloudError as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        created_message = await create_message(
            db,
            conversation,
            direction=MessageDirection.OUTBOUND,
            sender_type=body.message.sender_type,
            content=body.message.content,
            media_url=body.message.media_url,
            payload=message_payload,
            external_id=(
                str(ycloud_response.get("id"))
                if isinstance(ycloud_response, dict) and ycloud_response.get("id")
                else None
            ),
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

    return N8nInboundResponse(
        conversation=ConversationRead.model_validate(conversation),
        message=MessageRead.model_validate(created_message) if created_message else None,
    )
