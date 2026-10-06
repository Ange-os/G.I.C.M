"""Canal Instagram: provider vía n8n (puente hacia Meta Graph)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


class InstagramProviderError(Exception):
    """Error al enviar por Instagram (sin secretos)."""


@dataclass
class InstagramOutboundResult:
    external_id: str | None
    raw: dict[str, Any]


class MetaInstagramProvider:
    """Envía mensajes a Instagram usando n8n como transporte (Etapa 2.7)."""

    name = "meta"

    def is_configured(self) -> bool:
        return bool((settings.n8n_instagram_outbound_url or "").strip())

    async def send_text(
        self,
        *,
        recipient_id: str,
        text: str,
        conversation_id: str | None = None,
        message_id: str | None = None,
    ) -> InstagramOutboundResult:
        url = (settings.n8n_instagram_outbound_url or "").strip()
        if not url:
            raise InstagramProviderError(
                "Falta N8N_INSTAGRAM_OUTBOUND_URL (webhook n8n conversa-instagram-send)"
            )
        if not recipient_id.strip():
            raise InstagramProviderError("recipient_id de Instagram vacío")
        if not text.strip():
            raise InstagramProviderError("Mensaje vacío")

        payload = {
            "recipientId": recipient_id.strip(),
            "text": text.strip()[:1000],
            "conversationId": conversation_id,
            "messageId": message_id,
            "channel": "instagram",
        }
        headers = {"Content-Type": "application/json"}
        api_key = (settings.n8n_api_key or "").strip()
        if api_key:
            headers["X-N8N-API-Key"] = api_key

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise InstagramProviderError("No se pudo contactar al webhook de n8n (Instagram)") from exc

        if response.status_code >= 400:
            detail = response.text[:300] if response.text else str(response.status_code)
            raise InstagramProviderError(f"n8n Instagram outbound error: {detail}")

        try:
            raw = response.json()
        except ValueError:
            raw = {"status_code": response.status_code}
        if not isinstance(raw, dict):
            raw = {"result": raw}

        external_id = raw.get("message_id") or raw.get("mid") or raw.get("id")
        return InstagramOutboundResult(
            external_id=str(external_id) if external_id else None,
            raw=raw,
        )
