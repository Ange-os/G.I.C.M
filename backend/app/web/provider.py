"""Outbound canal web → xIA.ar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


class XiaWebProviderError(Exception):
    """Error al enviar a xIA (sin secretos)."""


@dataclass
class XiaOutboundResult:
    raw: dict[str, Any]


class XiaWebProvider:
    name = "xia"

    def is_configured(self) -> bool:
        return bool((settings.xia_outbound_url or "").strip())

    async def send_text(self, *, sender_id: str, text: str) -> XiaOutboundResult:
        url = (settings.xia_outbound_url or "").strip()
        if not url:
            raise XiaWebProviderError("Falta XIA_OUTBOUND_URL")
        if not sender_id.strip():
            raise XiaWebProviderError("senderId vacío")
        if not text.strip():
            raise XiaWebProviderError("Mensaje vacío")

        headers = {"Content-Type": "application/json"}
        api_key = (settings.xia_api_key or "").strip()
        if api_key:
            headers["X-XIA-API-Key"] = api_key

        payload = {"senderId": sender_id.strip(), "text": text.strip()}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise XiaWebProviderError("No se pudo contactar a xIA outbound") from exc

        if response.status_code >= 400:
            detail = response.text[:300] if response.text else str(response.status_code)
            raise XiaWebProviderError(f"xIA outbound error: {detail}")

        try:
            raw = response.json()
        except ValueError:
            raw = {"status_code": response.status_code}
        if not isinstance(raw, dict):
            raw = {"result": raw}
        return XiaOutboundResult(raw=raw)
