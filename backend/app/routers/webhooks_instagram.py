"""Webhook n8n → Conversa para Instagram (Etapa 2.7)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.instagram.inbound import persist_instagram_inbound
from app.schemas.instagram import InstagramN8nInbound, InstagramWebhookResponse
from app.services.events import publish_event
from app.services.handling import handling_mode_from_tags

router = APIRouter(prefix="/webhooks/n8n", tags=["webhooks-n8n-instagram"])


def _verify_n8n_key(x_n8n_api_key: str | None) -> None:
    if settings.n8n_api_key and x_n8n_api_key != settings.n8n_api_key:
        raise HTTPException(status_code=401, detail="Invalid n8n API key")


@router.post("/instagram", response_model=InstagramWebhookResponse)
async def n8n_instagram_inbound(
    body: InstagramN8nInbound,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_n8n_api_key: str | None = Header(default=None, alias="X-N8N-API-Key"),
) -> InstagramWebhookResponse:
    """
    Recibe mensajes de Instagram ya normalizados por n8n.

    Modalidad A: n8n sigue con el AI Agent; Conversa solo registra en Inbox.
    """
    _verify_n8n_key(x_n8n_api_key)

    if body.is_echo:
        return InstagramWebhookResponse(ok=True, skipped=True, skip_reason="echo")

    try:
        result = await persist_instagram_inbound(
            db,
            sender_id=body.sender_id,
            recipient_id=body.recipient_id,
            text=body.text,
            external_id=body.resolved_external_id(),
            contact_name=body.contact_name,
            raw=body.model_dump(by_alias=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    conversation = result.conversation
    message = result.message
    contact = conversation.contact

    if result.duplicate or message is None:
        return InstagramWebhookResponse(
            ok=True,
            conversation_id=conversation.id,
            duplicate=True,
        )

    event_payload = {
        "conversation": {
            "id": str(conversation.id),
            "status": conversation.status.value,
            "channel": conversation.channel.value,
            "tags": [tag.name for tag in conversation.tags],
            "handling_mode": handling_mode_from_tags(tag.name for tag in conversation.tags),
            "provider": "meta",
        },
        "contact": {
            "id": str(contact.id) if contact else str(result.contact_id),
            "phone": contact.phone if contact else None,
            "name": contact.name if contact else None,
            "instagram_sender_id": body.sender_id,
        },
        "message": {
            "id": str(message.id),
            "content": message.content,
            "direction": message.direction.value,
            "sender_type": message.sender_type.value,
        },
        "case": None,
    }
    background_tasks.add_task(publish_event, "conversation.message.created", event_payload)

    return InstagramWebhookResponse(
        ok=True,
        conversation_id=conversation.id,
        message_id=message.id,
        duplicate=False,
    )
