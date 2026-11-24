"""Lista EXPLÍCITA de plugins. Nada é carregado dinamicamente (segurança)."""
from __future__ import annotations

from .base import BatteryDevice
from .gamesir_nova2 import GameSirNova2
from .mchose_k7 import MchoseK7Ultra
from .mchose_v9 import MchoseV9Pro

ALL_DEVICE_CLASSES: tuple[type[BatteryDevice], ...] = (
    GameSirNova2,
    MchoseK7Ultra,
    MchoseV9Pro,
)

__all__ = ["ALL_DEVICE_CLASSES", "BatteryDevice", "GameSirNova2", "MchoseK7Ultra", "MchoseV9Pro"]
