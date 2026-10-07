"""Estado de atención humana vs automática (takeover).

Reutiliza tags existentes:
- bot-apagado → human
- bot-activo (o ausencia de bot-apagado) → automatic
"""

from __future__ import annotations

from typing import Iterable, Literal

HandlingMode = Literal["automatic", "human"]


def handling_mode_from_tags(tag_names: Iterable[str]) -> HandlingMode:
    names = set(tag_names)
    if "bot-apagado" in names:
        return "human"
    return "automatic"


def is_human_handling(tag_names: Iterable[str]) -> bool:
    return handling_mode_from_tags(tag_names) == "human"
