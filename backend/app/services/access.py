"""Alcance de canales e inbox según el rol del panel."""

from __future__ import annotations

from fastapi import HTTPException

from app.models.entities import Channel, Conversation, User, UserRole

# Roles que ven todos los canales.
FULL_INBOX_ROLES = frozenset({UserRole.ADMIN, UserRole.CONSEJO})


def allowed_channels(user: User) -> frozenset[Channel] | None:
    """None = todos los canales. Conjunto = solo esos."""
    if user.role == UserRole.MUESTRA_INSTA:
        return frozenset({Channel.INSTAGRAM})
    if user.role in FULL_INBOX_ROLES:
        return None
    return frozenset({Channel.INSTAGRAM})


def can_access_conversation(user: User, conversation: Conversation) -> bool:
    channels = allowed_channels(user)
    if channels is None:
        return True
    return conversation.channel in channels


def require_conversation_access(user: User, conversation: Conversation) -> None:
    if not can_access_conversation(user, conversation):
        raise HTTPException(status_code=404, detail="Conversation not found")
