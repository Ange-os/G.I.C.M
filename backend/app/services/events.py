import asyncio
import json
import logging
from typing import Any

import httpx
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None
REDIS_TIMEOUT_SECONDS = 2.0
N8N_TIMEOUT_SECONDS = 5.0


async def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
            socket_timeout=REDIS_TIMEOUT_SECONDS,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


# Canales cuyo bot vive fuera de Conversa (n8n Instagram / xIA). No disparar conversa-events.
_CHANNELS_SKIP_N8N_BOT = frozenset({"instagram", "web"})


def _channel_from_payload(payload: dict[str, Any]) -> str:
    conversation = payload.get("conversation") or {}
    if isinstance(conversation, dict):
        raw = conversation.get("channel") or ""
    else:
        raw = ""
    return str(raw).strip().lower()


def _should_forward_to_n8n_bot(payload: dict[str, Any]) -> bool:
    """Solo WhatsApp usa el bot de N8N_WEBHOOK_URL (conversa-events)."""
    channel = _channel_from_payload(payload)
    if not channel:
        return True
    return channel not in _CHANNELS_SKIP_N8N_BOT


async def publish_event(event: str, payload: dict[str, Any]) -> None:
    """Publica evento en Redis y opcionalmente reenvía a n8n. Nunca bloquea indefinidamente."""
    envelope = {"event": event, **payload}
    serialized = json.dumps(envelope, default=str)

    try:
        client = await get_redis()
        await asyncio.wait_for(
            client.publish("conversa:events", serialized),
            timeout=REDIS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("Redis publish skipped: %s", exc)

    if settings.n8n_webhook_url and _should_forward_to_n8n_bot(payload):
        try:
            async with httpx.AsyncClient(timeout=N8N_TIMEOUT_SECONDS) as http:
                await http.post(settings.n8n_webhook_url, json=envelope)
        except httpx.HTTPError as exc:
            logger.warning("n8n webhook skipped: %s", exc)
    elif settings.n8n_webhook_url:
        logger.debug(
            "n8n conversa-events omitido para canal=%s",
            _channel_from_payload(payload) or "?",
        )