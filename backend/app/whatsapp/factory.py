"""Factory de providers WhatsApp."""

from __future__ import annotations

from app.whatsapp.base import PROVIDER_META, PROVIDER_YCLOUD, WhatsAppProvider, WhatsAppProviderError
from app.whatsapp.conversation_provider import normalize_provider
from app.whatsapp.meta_provider import MetaWhatsAppProvider
from app.whatsapp.ycloud_provider import YCloudWhatsAppProvider

_YCLOUD = YCloudWhatsAppProvider()
_META = MetaWhatsAppProvider()


def get_whatsapp_provider(provider: str | None) -> WhatsAppProvider:
    name = normalize_provider(provider)
    if name == PROVIDER_META:
        return _META
    if name == PROVIDER_YCLOUD:
        return _YCLOUD
    raise WhatsAppProviderError(f"Provider WhatsApp desconocido: {provider}")


def list_provider_status() -> list[dict]:
    from app.config import settings

    return [
        {
            "id": PROVIDER_YCLOUD,
            "configured": bool((settings.ycloud_api_key or "").strip()),
            "default": normalize_provider(settings.whatsapp_default_provider) == PROVIDER_YCLOUD,
        },
        {
            "id": PROVIDER_META,
            "configured": _META.is_configured(),
            "default": normalize_provider(settings.whatsapp_default_provider) == PROVIDER_META,
        },
    ]
