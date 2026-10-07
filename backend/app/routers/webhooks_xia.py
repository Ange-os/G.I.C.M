"""Webhook xIA.ar → Conversa (canal web)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.xia import XiaWebInbound, XiaWebhookResponse
from app.services.events import publish_event
from app.services.handling import handling_mode_from_tags
from app.web.inbound import persist_web_inbound

router = APIRouter(prefix="/webhooks/xia", tags=["webhooks-xia"])


def _verify_xia_key(x_xia_api_key: str | None) -> None:
    expected = (settings.xia_api_key or settings.n8n_api_key or "").strip()
    if expected and (x_xia_api_key or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid X-XIA-API-Key")


@router.post("/inbound", response_model=XiaWebhookResponse)
async def xia_web_inbound(
    body: XiaWebInbound,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_xia_api_key: str | None = Header(default=None, alias="X-XIA-API-Key"),
) -> XiaWebhookResponse:
    """Espeja mensajes de xIA.ar (usuario o bot) en el Inbox como canal web."""
    _verify_xia_key(x_xia_api_key)

    try:
        result = await persist_web_inbound(
            db,
            sender_id=body.sender_id,
            text=body.text,
            external_id=(body.external_message_id or "").strip() or None,
            role=body.role,
            email=body.email,
            name=body.name,
            picture=body.picture,
            external_conversation_id=body.external_conversation_id,
            source=body.source,
            raw=body.model_dump(by_alias=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    conversation = result.conversation
    message = result.message
    contact = conversation.contact

    if result.duplicate or message is None:
        return XiaWebhookResponse(
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
            "provider": "xia",
        },
        "contact": {
            "id": str(contact.id) if contact else str(result.contact_id),
            "phone": contact.phone if contact else None,
            "name": contact.name if contact else None,
            "xia_sender_id": body.sender_id,
            "email": body.email,
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

    return XiaWebhookResponse(
        ok=True,
        conversation_id=conversation.id,
        message_id=message.id,
        duplicate=False,
    )
