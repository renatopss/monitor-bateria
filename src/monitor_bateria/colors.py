"""Paleta de cores dos ícones. Puro (sem Pillow/tkinter), fácil de testar."""
from __future__ import annotations

from dataclasses import dataclass

HEX_DIGITS = frozenset("0123456789abcdefABCDEF")

DEFAULT_COLORS: dict[str, str] = {
    "ok": "#238c3c",    # bateria boa
    "mid": "#d68c14",   # bateria média
    "low": "#c82d3c",   # bateria baixa
    "none": "#6e6e6e",  # sem leitura
    "text": "#ffffff",  # número e desenho
    "bg": "#1f1f1f",    # fundo do widget da barra de tarefas
    "charge": "#ffd400",  # raio de "carregando"
}
COLOR_LABELS: dict[str, str] = {
    "ok": "Bateria boa",
    "mid": "Bateria média",
    "low": "Bateria baixa",
    "none": "Sem leitura",
    "text": "Número e desenho",
    "bg": "Fundo do widget",
    "charge": "Raio (carregando)",
}
# Contorno da caixa do número na bandeja, por tipo de aparelho: cores de fora para dentro.
DEFAULT_BORDERS: dict[str, list[str]] = {
    "controller": ["#9e9e9e"],             # controle: cinza
    "mouse": ["#d4af37", "#000000"],       # mouse: dourado e preto
    "headset": ["#e53935", "#000000"],     # headset: vermelho e preto
}
BORDER_LABELS: dict[str, str] = {"controller": "Contorno controle", "mouse": "Contorno mouse", "headset": "Contorno headset"}
MAX_BORDER_RINGS = 3
DEFAULT_MID_PERCENT = 50
MIN_MID, MAX_MID = 10, 90


def normalize_hex(value: object) -> str | None:
    """Devolve '#rrggbb' minúsculo se for válido; senão None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) == 7 and text[0] == "#" and all(ch in HEX_DIGITS for ch in text[1:]):
        return text.lower()
    return None


def hex_to_rgba(value: str) -> tuple[int, int, int, int]:
    h = normalize_hex(value)
    if h is None:
        raise ValueError("cor inválida")
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 255


def parse_colors(raw: object) -> dict[str, str]:
    """Aceita só as chaves conhecidas com cores válidas; o resto vira o padrão."""
    colors = dict(DEFAULT_COLORS)
    if isinstance(raw, dict):
        for key in DEFAULT_COLORS:
            valid = normalize_hex(raw.get(key))
            if valid:
                colors[key] = valid
    return colors


def parse_border(raw: object) -> list[str] | None:
    """Aceita lista de cores (ou texto '#a,#b'); vazio = sem contorno. Inválido = None."""
    if isinstance(raw, str):
        raw = [part for part in raw.replace(";", ",").split(",") if part.strip()]
    if not isinstance(raw, list) or len(raw) > MAX_BORDER_RINGS:
        return None
    rings = [normalize_hex(v) for v in raw]
    return None if any(r is None for r in rings) else rings  # type: ignore[return-value]


def parse_borders(raw: object) -> dict[str, list[str]]:
    """Só os tipos conhecidos com contornos válidos; o resto vira o padrão."""
    borders = {k: list(v) for k, v in DEFAULT_BORDERS.items()}
    if isinstance(raw, dict):
        for kind in DEFAULT_BORDERS:
            valid = parse_border(raw.get(kind))
            if valid is not None:
                borders[kind] = valid
    return borders


def clamp_mid(mid: int, low: int) -> int:
    return max(MIN_MID, min(MAX_MID, max(mid, low + 5)))


@dataclass(frozen=True)
class Palette:
    colors: dict[str, str]
    low_percent: int = 20
    mid_percent: int = DEFAULT_MID_PERCENT

    def hex_for(self, percent: int | None) -> str:
        if percent is None:
            return self.colors["none"]
        if percent <= self.low_percent:
            return self.colors["low"]
        if percent <= self.mid_percent:
            return self.colors["mid"]
        return self.colors["ok"]

    def rgba_for(self, percent: int | None) -> tuple[int, int, int, int]:
        return hex_to_rgba(self.hex_for(percent))

    def text_rgba(self) -> tuple[int, int, int, int]:
        return hex_to_rgba(self.colors["text"])


DEFAULT_PALETTE = Palette(dict(DEFAULT_COLORS))
