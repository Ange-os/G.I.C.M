from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.conversation import YCloudWebhookResponse
from app.services.conversation import (
    create_conversation,
    create_message,
    get_conversation_with_relations,
    get_open_conversation,
    get_or_create_contact,
)
from app.services.events import publish_event
from app.services.ycloud import parse_ycloud_inbound

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

    contact = await get_or_create_contact(db, phone=phone, name=parsed.get("contact_name"))
    conversation = await get_open_conversation(db, contact.id, channel=parsed["channel"])
    if not conversation:
        conversation = await create_conversation(
            db,
            contact_id=contact.id,
            channel=parsed["channel"],
            ycloud_phone_number_id=parsed.get("ycloud_phone_number_id"),
        )

    message = await create_message(
        db,
        conversation,
        direction=parsed["direction"],
        sender_type=parsed["sender_type"],
        content=parsed.get("content"),
        media_url=parsed.get("media_url"),
        payload={"raw": parsed.get("raw", {})},
        external_id=parsed.get("external_id"),
    )

    if message is None:
        return YCloudWebhookResponse(
            ok=True,
            conversation_id=conversation.id,
            duplicate=True,
        )

    conversation = await get_conversation_with_relations(db, conversation.id)
    if conversation is None:
        raise HTTPException(status_code=500, detail="Conversation not found after save")

    event_payload = {
        "conversation": {
            "id": str(conversation.id),
            "status": conversation.status.value,
            "channel": conversation.channel.value,
            "tags": [tag.name for tag in conversation.tags],
        },
        "contact": {
            "id": str(contact.id),
            "phone": contact.phone,
            "name": contact.name,
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
    )
