"""Permisos del agente por rol de aplicación."""

from __future__ import annotations

from app.models.entities import User, UserRole

# Tools de lectura: admin y consejo (dominio + inbox).
READ_TOOLS = frozenset(
    {
        "search_organization",
        "search_agreement",
        "get_agreement_summary",
        "search_doctors",
        "search_conversation",
    }
)

# Demo Instagram: solo inbox del canal Instagram.
MUESTRA_INSTA_TOOLS = frozenset({"search_conversation"})

# Tools que preparan acciones (siempre requieren confirmación UX).
ACTION_TOOLS = frozenset(
    {
        "prepare_email",
        "prepare_suspend_agreement",
        "prepare_activate_agreement",
    }
)


def allowed_tool_names(user: User) -> set[str]:
    if user.role == UserRole.MUESTRA_INSTA:
        return set(MUESTRA_INSTA_TOOLS)
    names = set(READ_TOOLS)
    if user.role == UserRole.ADMIN:
        names |= ACTION_TOOLS
    return names


def can_execute_action(user: User, action: str) -> bool:
    if user.role == UserRole.MUESTRA_INSTA:
        return False
    if action in {"send_email", "suspend_agreement", "activate_agreement"}:
        return user.role == UserRole.ADMIN
    return False
