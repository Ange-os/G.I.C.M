from typing import Any

from app.models.entities import Channel, MessageDirection, SenderType


def _extract_text(body: dict[str, Any]) -> str | None:
    if "text" in body and isinstance(body["text"], dict):
        return body["text"].get("body") or body["text"].get("text")
    if "text" in body and isinstance(body["text"], str):
        return body["text"]
    if "body" in body:
        return str(body["body"])
    if "content" in body:
        return str(body["content"])
    return None


def _extract_media_url(body: dict[str, Any]) -> str | None:
    for key in ("image", "document", "audio", "video", "sticker"):
        media = body.get(key)
        if isinstance(media, dict):
            return media.get("link") or media.get("url")
    return body.get("media_url") or body.get("mediaUrl")


def _unwrap_ycloud_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """YCloud vía n8n webhook suele llegar como { body: { whatsappInboundMessage: ... } }."""
    if "whatsappInboundMessage" in payload or "whatsapp_inbound_message" in payload:
        return payload
    body = payload.get("body")
    if isinstance(body, dict):
        return body
    return payload


def parse_ycloud_inbound(payload: dict[str, Any]) -> dict[str, Any] | None:
    """
    Normaliza distintos formatos de webhook YCloud a un dict interno.
    Retorna None si el evento no es un mensaje entrante procesable.
    """
    payload = _unwrap_ycloud_payload(payload)
    event_type = payload.get("type") or payload.get("event")

    # Formato documentado YCloud: whatsapp.inbound_message.received
    inbound = payload.get("whatsappInboundMessage") or payload.get("whatsapp_inbound_message")
    if inbound:
        msg_type = inbound.get("type", "text")
        content = None
        media_url = None

        if msg_type == "text":
            content = _extract_text(inbound)
        else:
            media_url = _extract_media_url(inbound)
            content = inbound.get("caption")

        return {
            "external_id": inbound.get("wamid") or inbound.get("id"),
            "from_phone": inbound.get("from") or inbound.get("customerPhone"),
            "to_phone": inbound.get("to") or inbound.get("businessPhone"),
            "ycloud_phone_number_id": inbound.get("phoneNumberId") or inbound.get("phone_number_id"),
            "contact_name": inbound.get("customerProfile", {}).get("name")
            if isinstance(inbound.get("customerProfile"), dict)
            else inbound.get("fromName"),
            "content": content,
            "media_url": media_url,
            "channel": Channel.WHATSAPP,
            "sender_type": SenderType.CONTACT,
            "direction": MessageDirection.INBOUND,
            "raw": payload,
        }

    # Formato genérico / alternativo
    if event_type in (None, "message", "messages", "inbound"):
        data = payload.get("data") or payload.get("message") or payload
        from_phone = data.get("from") or data.get("from_phone") or data.get("customerPhone")
        if not from_phone:
            return None

        return {
            "external_id": data.get("id") or data.get("wamid") or data.get("message_id"),
            "from_phone": from_phone,
            "to_phone": data.get("to") or data.get("to_phone"),
            "ycloud_phone_number_id": data.get("phoneNumberId") or data.get("phone_number_id"),
            "contact_name": data.get("fromName") or data.get("name"),
            "content": _extract_text(data) or data.get("message"),
            "media_url": _extract_media_url(data),
            "channel": Channel.WHATSAPP,
            "sender_type": SenderType.CONTACT,
            "direction": MessageDirection.INBOUND,
            "raw": payload,
        }

    return None
