"""Adapter YCloud sobre el envío existente."""

from __future__ import annotations

from app.services.ycloud_outbound import YCloudError, send_whatsapp_text
from app.whatsapp.base import PROVIDER_YCLOUD, OutboundResult, WhatsAppProviderError


class YCloudWhatsAppProvider:
    name = PROVIDER_YCLOUD

    async def send_text(
        self,
        *,
        to: str,
        text: str,
        phone_number_id: str | None = None,
    ) -> OutboundResult:
        try:
            raw = await send_whatsapp_text(to=to, text=text)
        except YCloudError as exc:
            raise WhatsAppProviderError(str(exc)) from exc
        external_id = raw.get("id")
        return OutboundResult(
            external_id=str(external_id) if external_id else None,
            raw=raw,
        )
