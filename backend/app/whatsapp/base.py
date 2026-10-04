"""Providers de WhatsApp: YCloud (actual) y Meta Cloud API (experimento)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.models.entities import Channel, MessageDirection, SenderType

PROVIDER_YCLOUD = "ycloud"
PROVIDER_META = "meta"
VALID_PROVIDERS = frozenset({PROVIDER_YCLOUD, PROVIDER_META})


class WhatsAppProviderError(Exception):
    """Error normalizado del proveedor de WhatsApp (sin secretos)."""


@dataclass
class NormalizedInbound:
    """Evento de WhatsApp normalizado, independiente del proveedor."""

    provider: str
    external_id: str | None
    from_phone: str
    to_phone: str | None = None
    phone_number_id: str | None = None
    contact_name: str | None = None
    content: str | None = None
    media_url: str | None = None
    media_type: str | None = None
    channel: Channel = Channel.WHATSAPP
    sender_type: SenderType = SenderType.CONTACT
    direction: MessageDirection = MessageDirection.INBOUND
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundResult:
    external_id: str | None
    raw: dict[str, Any] = field(default_factory=dict)


class WhatsAppProvider(Protocol):
    name: str

    async def send_text(self, *, to: str, text: str, phone_number_id: str | None = None) -> OutboundResult:
        ...
