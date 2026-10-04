"""Meta WhatsApp Cloud API: parseo de webhooks y envío outbound."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.models.entities import Channel, MessageDirection, SenderType
from app.whatsapp.base import (
    PROVIDER_META,
    NormalizedInbound,
    OutboundResult,
    WhatsAppProviderError,
)

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"


class MetaWhatsAppProvider:
    name = PROVIDER_META

    def is_configured(self) -> bool:
        return bool(
            (settings.meta_whatsapp_access_token or "").strip()
            and (settings.meta_whatsapp_phone_number_id or "").strip()
        )

    async def send_text(
        self,
        *,
        to: str,
        text: str,
        phone_number_id: str | None = None,
    ) -> OutboundResult:
        token = (settings.meta_whatsapp_access_token or "").strip()
        phone_id = (phone_number_id or settings.meta_whatsapp_phone_number_id or "").strip()
        if not token:
            raise WhatsAppProviderError("Falta META_WHATSAPP_ACCESS_TOKEN")
        if not phone_id:
            raise WhatsAppProviderError("Falta META_WHATSAPP_PHONE_NUMBER_ID")

        to_digits = "".join(ch for ch in to if ch.isdigit())
        if not to_digits:
            raise WhatsAppProviderError("Número de destino inválido")

        url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_digits,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise WhatsAppProviderError("No se pudo contactar a Meta Cloud API") from exc

        if response.status_code >= 400:
            raise WhatsAppProviderError(_meta_error_message(response))

        data = response.json()
        messages = data.get("messages") or []
        external_id = None
        if messages and isinstance(messages[0], dict):
            external_id = messages[0].get("id")
        return OutboundResult(
            external_id=str(external_id) if external_id else None,
            raw=data,
        )


def parse_meta_inbound(payload: dict[str, Any]) -> list[NormalizedInbound]:
    """Extrae mensajes de un webhook de Meta (puede traer varios)."""
    if payload.get("object") not in (None, "whatsapp_business_account"):
        # Algunos wrappers no mandan object; igual intentamos entry
        if "entry" not in payload:
            return []

    events: list[NormalizedInbound] = []
    for entry in payload.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        for change in entry.get("changes") or []:
            if not isinstance(change, dict):
                continue
            value = change.get("value") or {}
            if not isinstance(value, dict):
                continue
            # Solo mensajes entrantes (ignorar statuses)
            messages = value.get("messages") or []
            if not messages:
                continue

            metadata = value.get("metadata") or {}
            phone_number_id = metadata.get("phone_number_id")
            display_phone = metadata.get("display_phone_number")
            contacts = value.get("contacts") or []
            contact_name = None
            if contacts and isinstance(contacts[0], dict):
                profile = contacts[0].get("profile") or {}
                if isinstance(profile, dict):
                    contact_name = profile.get("name")

            for message in messages:
                if not isinstance(message, dict):
                    continue
                from_phone = message.get("from")
                if not from_phone:
                    continue
                msg_type = message.get("type") or "text"
                content = None
                media_url = None
                media_type = None

                if msg_type == "text":
                    text = message.get("text") or {}
                    content = text.get("body") if isinstance(text, dict) else None
                elif msg_type in {"image", "document", "audio", "video", "sticker"}:
                    media = message.get(msg_type) or {}
                    media_type = msg_type
                    if isinstance(media, dict):
                        media_url = media.get("id")  # id de media en Meta; URL se resuelve luego
                        content = media.get("caption")
                        if msg_type == "document" and media.get("filename"):
                            content = content or media.get("filename")
                elif msg_type == "button":
                    button = message.get("button") or {}
                    content = button.get("text") if isinstance(button, dict) else None
                elif msg_type == "interactive":
                    interactive = message.get("interactive") or {}
                    content = _interactive_text(interactive)
                else:
                    content = f"[{msg_type}]"

                events.append(
                    NormalizedInbound(
                        provider=PROVIDER_META,
                        external_id=message.get("id"),
                        from_phone=str(from_phone),
                        to_phone=str(display_phone) if display_phone else None,
                        phone_number_id=str(phone_number_id) if phone_number_id else None,
                        contact_name=contact_name,
                        content=content,
                        media_url=str(media_url) if media_url else None,
                        media_type=media_type,
                        channel=Channel.WHATSAPP,
                        sender_type=SenderType.CONTACT,
                        direction=MessageDirection.INBOUND,
                        raw={"entry_id": entry.get("id"), "message": message, "metadata": metadata},
                    )
                )
    return events


def _interactive_text(interactive: Any) -> str | None:
    if not isinstance(interactive, dict):
        return None
    for key in ("button_reply", "list_reply"):
        reply = interactive.get(key)
        if isinstance(reply, dict):
            return reply.get("title") or reply.get("id")
    return None


def _meta_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        error = body.get("error") or {}
        message = error.get("message")
        code = error.get("code")
        if message and code is not None:
            return f"Meta error {code}: {message}"
        if message:
            return f"Meta error: {message}"
    except ValueError:
        pass
    return f"Meta respondió {response.status_code}"
