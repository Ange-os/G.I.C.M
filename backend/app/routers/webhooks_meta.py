"""Webhook oficial Meta WhatsApp Cloud API (experimento, convive con YCloud)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.conversation import MetaWebhookResponse
from app.services.events import publish_event
from app.whatsapp.base import PROVIDER_META
from app.whatsapp.inbound import persist_inbound
from app.whatsapp.meta_provider import parse_meta_inbound

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/meta", tags=["webhooks-meta"])


@router.get("/whatsapp")
async def meta_whatsapp_verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> Response:
    """Verificación inicial del webhook en Meta Developer Console."""
    expected = (settings.meta_whatsapp_verify_token or "").strip()
    if hub_mode == "subscribe" and expected and hub_verify_token == expected and hub_challenge:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verificación Meta rechazada")


@router.post("/whatsapp", response_model=MetaWebhookResponse)
async def meta_whatsapp_inbound(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> MetaWebhookResponse:
    """Recibe mensajes entrantes de WhatsApp vía Meta Cloud API."""
    raw_body = await request.body()
    _verify_meta_signature(raw_body, x_hub_signature_256)

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="JSON inválido") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON inválido")

    events = parse_meta_inbound(payload)
    if not events:
        return MetaWebhookResponse(ok=True, processed=0)

    processed = 0
    last_conversation_id = None
    last_message_id = None
    any_duplicate = False

    for event in events:
        result = await persist_inbound(db, event)
        last_conversation_id = result.conversation.id
        if result.duplicate or result.message is None:
            any_duplicate = True
            continue

        processed += 1
        last_message_id = result.message.id
        conversation = result.conversation
        contact = conversation.contact
        message = result.message

        event_payload = {
            "conversation": {
                "id": str(conversation.id),
                "status": conversation.status.value,
                "channel": conversation.channel.value,
                "tags": [tag.name for tag in conversation.tags],
                "whatsapp_provider": PROVIDER_META,
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

    return MetaWebhookResponse(
        ok=True,
        processed=processed,
        conversation_id=last_conversation_id,
        message_id=last_message_id,
        duplicate=any_duplicate and processed == 0,
    )


def _verify_meta_signature(raw_body: bytes, header_value: str | None) -> None:
    secret = (settings.meta_whatsapp_app_secret or "").strip()
    if not secret:
        # App secret opcional en el experimento local.
        return
    if not header_value or not header_value.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Falta firma X-Hub-Signature-256")
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    received = header_value.removeprefix("sha256=")
    if not hmac.compare_digest(expected, received):
        logger.warning("Firma Meta inválida")
        raise HTTPException(status_code=401, detail="Firma Meta inválida")
