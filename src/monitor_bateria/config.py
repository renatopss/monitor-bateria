"""Configuração em JSON dentro de %LOCALAPPDATA%\\monitor-bateria. Só dados, nunca código."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .colors import DEFAULT_COLORS, DEFAULT_MID_PERCENT, MAX_MID, MIN_MID, Palette, clamp_mid, parse_colors

log = logging.getLogger(__name__)

MAX_CONFIG_BYTES = 16 * 1024
MIN_INTERVAL_MIN, MAX_INTERVAL_MIN = 5, 1440
MIN_LOW, MAX_LOW = 5, 50


def config_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "monitor-bateria"


@dataclass(frozen=True)
class Config:
    interval_minutes: int = 30
    low_battery_percent: int = 20
    devices: dict[str, bool] = field(default_factory=dict)
    colors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_COLORS))
    mid_percent: int = DEFAULT_MID_PERCENT
    icon_style: str = "grande"  # "completo" = desenho em cima; "lado" = desenho à esquerda; "grande" = só número
    game_mode: bool = True  # tela cheia: esconde o widget e não lê os aparelhos
    widget: bool = True  # widget na barra de tarefas (ícone + número ao lado)
    widget_pos: tuple[int, int] | None = None
    tray_mode: str = "separado"  # "separado" = um ícone por aparelho; "unico" = só o menor

    @property
    def palette(self) -> Palette:
        return Palette(
            dict(self.colors),
            low_percent=self.low_battery_percent,
            mid_percent=clamp_mid(self.mid_percent, self.low_battery_percent),
        )

    @property
    def interval_seconds(self) -> int:
        return self.interval_minutes * 60

    def is_enabled(self, device_cls) -> bool:
        return self.devices.get(device_cls.device_id, device_cls.enabled_by_default)


def _clamped_int(value: object, lo: int, hi: int, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(lo, min(hi, value))


def _parse_pos(value: object) -> tuple[int, int] | None:
    if (
        isinstance(value, list) and len(value) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) and -20000 <= v <= 20000 for v in value)
    ):
        return value[0], value[1]
    return None


def parse_config(raw: object) -> Config:
    if not isinstance(raw, dict):
        return Config()
    devices_raw = raw.get("devices", {})
    devices: dict[str, bool] = {}
    if isinstance(devices_raw, dict):
        for key, value in devices_raw.items():
            if isinstance(key, str) and isinstance(value, bool) and len(key) <= 64:
                devices[key] = value
    return Config(
        interval_minutes=_clamped_int(raw.get("interval_minutes"), MIN_INTERVAL_MIN, MAX_INTERVAL_MIN, 30),
        low_battery_percent=_clamped_int(raw.get("low_battery_percent"), MIN_LOW, MAX_LOW, 20),
        devices=devices,
        colors=parse_colors(raw.get("colors")),
        mid_percent=_clamped_int(raw.get("mid_percent"), MIN_MID, MAX_MID, DEFAULT_MID_PERCENT),
        icon_style=raw.get("icon_style") if raw.get("icon_style") in ("completo", "grande", "lado") else "grande",
        game_mode=raw.get("game_mode") if isinstance(raw.get("game_mode"), bool) else True,
        widget=raw.get("widget") if isinstance(raw.get("widget"), bool) else True,
        widget_pos=_parse_pos(raw.get("widget_pos")),
        tray_mode=raw.get("tray_mode") if raw.get("tray_mode") in ("separado", "unico") else "separado",
    )


def load_config(path: Path) -> Config:
    try:
        if not path.exists():
            return Config()
        if path.stat().st_size > MAX_CONFIG_BYTES:
            log.warning("config grande demais; usando padrões")
            return Config()
        return parse_config(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        log.warning("config inválida; usando padrões")
        return Config()


def write_default_config(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    default = {
        "interval_minutes": 30,
        "low_battery_percent": 20,
        "tray_mode": "separado",
        "icon_style": "grande",
        "widget": True,
        "game_mode": True,
        "mid_percent": DEFAULT_MID_PERCENT,
        "colors": dict(DEFAULT_COLORS),
        "devices": {"gamesir_nova2": True, "mchose_k7": True, "mchose_v9": True},
    }
    path.write_text(json.dumps(default, indent=2), encoding="utf-8")


def _update_raw(path: Path, mutate) -> None:
    """Lê o config atual (se válido), aplica `mutate(raw)` e grava de forma atômica."""
    raw: dict = {}
    try:
        if path.exists() and path.stat().st_size <= MAX_CONFIG_BYTES:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            raw = loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        raw = {}
    mutate(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(raw, handle, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_colors(path: Path, colors: dict[str, str], mid_percent: int, icon_style: str | None = None) -> None:
    """Grava só as cores, o limite 'média' e o estilo, preservando o resto do arquivo."""

    def mutate(raw: dict) -> None:
        raw["colors"] = parse_colors(colors)
        raw["mid_percent"] = _clamped_int(mid_percent, MIN_MID, MAX_MID, DEFAULT_MID_PERCENT)
        if icon_style in ("completo", "grande", "lado"):
            raw["icon_style"] = icon_style

    _update_raw(path, mutate)


def save_widget_pos(path: Path, x: int, y: int) -> None:
    pos = _parse_pos([x, y])
    if pos is not None:
        _update_raw(path, lambda raw: raw.__setitem__("widget_pos", [pos[0], pos[1]]))
