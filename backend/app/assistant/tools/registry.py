"""Registro de tools disponibles para el agente."""

from __future__ import annotations

from app.assistant.permissions import allowed_tool_names
from app.assistant.tools.actions import ACTION_TOOL_SPECS
from app.assistant.tools.base import ToolSpec
from app.assistant.tools.read import READ_TOOL_SPECS
from app.models.entities import User

_ALL: dict[str, ToolSpec] = {spec.name: spec for spec in [*READ_TOOL_SPECS, *ACTION_TOOL_SPECS]}


def get_tool(name: str) -> ToolSpec | None:
    return _ALL.get(name)


def tools_for_user(user: User) -> list[ToolSpec]:
    allowed = allowed_tool_names(user)
    return [spec for name, spec in _ALL.items() if name in allowed]


def openai_tools_for_user(user: User) -> list[dict]:
    return [spec.openai_schema() for spec in tools_for_user(user)]
