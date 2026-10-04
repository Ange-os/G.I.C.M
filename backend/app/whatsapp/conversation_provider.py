"""Utilidades de provider en conversaciones."""

from __future__ import annotations

from app.config import settings
from app.models.entities import Conversation
from app.whatsapp.base import PROVIDER_YCLOUD, VALID_PROVIDERS


def normalize_provider(value: str | None) -> str:
    name = (value or "").strip().lower()
    if name in VALID_PROVIDERS:
        return name
    default = (settings.whatsapp_default_provider or PROVIDER_YCLOUD).strip().lower()
    return default if default in VALID_PROVIDERS else PROVIDER_YCLOUD


def get_conversation_provider(conversation: Conversation) -> str:
    meta = conversation.metadata_ or {}
    stored = meta.get("whatsapp_provider")
    if isinstance(stored, str) and stored.strip():
        return normalize_provider(stored)
    return normalize_provider(settings.whatsapp_default_provider)


def set_conversation_provider(conversation: Conversation, provider: str) -> None:
    meta = dict(conversation.metadata_ or {})
    meta["whatsapp_provider"] = normalize_provider(provider)
    conversation.metadata_ = meta
