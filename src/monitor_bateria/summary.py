"""Textos e valores derivados das leituras. Puro, sem Windows, fácil de testar."""
from __future__ import annotations

from typing import Sequence

from .models import Reading, Status

MAX_TOOLTIP = 127  # limite do Windows para o texto do ícone da bandeja


def lowest_percent(readings: Sequence[Reading]) -> int | None:
    values = [r.percent for r in readings if r.status is Status.OK and r.percent is not None]
    return min(values) if values else None


def tooltip(readings: Sequence[Reading]) -> str:
    if not readings:
        return "Monitor de bateria"
    text = "\n".join(r.short() for r in readings)
    return text if len(text) <= MAX_TOOLTIP else text[: MAX_TOOLTIP - 1] + "…"
