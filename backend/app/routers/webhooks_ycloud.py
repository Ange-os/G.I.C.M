"""Webhook YCloud: mantiene el flujo actual y marca provider=ycloud."""

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.conversation import YCloudWebhookResponse
from app.services.events import publish_event
from app.services.ycloud import parse_ycloud_inbound
from app.whatsapp.base import PROVIDER_YCLOUD, NormalizedInbound
from app.whatsapp.inbound import persist_inbound

router = APIRouter(prefix="/webhooks/ycloud", tags=["webhooks-ycloud"])


def _verify_ycloud_secret(x_ycloud_signature: str | None) -> None:
    if settings.ycloud_webhook_secret and x_ycloud_signature != settings.ycloud_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid YCloud webhook secret")


@router.post("/inbound", response_model=YCloudWebhookResponse)
async def ycloud_inbound(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_ycloud_signature: str | None = Header(default=None, alias="X-YCloud-Signature"),
) -> YCloudWebhookResponse:
    """Recibe mensajes entrantes de WhatsApp vía YCloud."""
    _verify_ycloud_secret(x_ycloud_signature)

    payload = await request.json()
    parsed = parse_ycloud_inbound(payload)
    if not parsed:
        return YCloudWebhookResponse(ok=True)

    phone = parsed["from_phone"]
    if not phone:
        raise HTTPException(status_code=422, detail="Missing sender phone in YCloud payload")

    event = NormalizedInbound(
        provider=PROVIDER_YCLOUD,
        external_id=parsed.get("external_id"),
        from_phone=phone,
        to_phone=parsed.get("to_phone"),
        phone_number_id=parsed.get("ycloud_phone_number_id"),
        contact_name=parsed.get("contact_name"),
        content=parsed.get("content"),
        media_url=parsed.get("media_url"),
        channel=parsed["channel"],
        sender_type=parsed["sender_type"],
        direction=parsed["direction"],
        raw=parsed.get("raw") or payload,
    )

    result = await persist_inbound(db, event)
    conversation = result.conversation
    message = result.message
    contact = conversation.contact

    if result.duplicate or message is None:
        return YCloudWebhookResponse(
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
            "whatsapp_provider": PROVIDER_YCLOUD,
        },
        "contact": {
            "id": str(contact.id) if contact else str(result.contact_id),
            "phone": contact.phone if contact else None,
            "name": contact.name if contact else None,
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

    return YCloudWebhookResponse(
        ok=True,
        conversation_id=conversation.id,
        message_id=message.id,
        duplicate=False,
    )
