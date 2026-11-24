from pathlib import Path

import pytest

from monitor_bateria import icon as icon_mod
from monitor_bateria.icon import GRAY, GREEN, RED, color_for, render_icon
from monitor_bateria.models import Reading, Status
from monitor_bateria.summary import MAX_TOOLTIP, lowest_percent, tooltip

SNAP = Path(__file__).parent / "snapshots" / "tooltip.txt"


@pytest.mark.parametrize("pct,color", [(None, GRAY), (5, RED), (20, RED), (66, GREEN), (100, GREEN)])
def test_colors(pct, color):
    assert color_for(pct) == color


@pytest.mark.parametrize("pct", [None, 0, 7, 66, 100])
def test_icon_renders(pct):
    img = render_icon(pct)
    assert img.size == (64, 64) and img.mode == "RGBA"


def test_icon_survives_missing_scalable_font(monkeypatch):
    real = icon_mod.ImageFont.load_default

    def fake(size=None):
        if size is not None:
            raise TypeError("sem fonte escalável")
        return real()

    monkeypatch.setattr(icon_mod.ImageFont, "load_default", fake)
    assert render_icon(66).size == (64, 64)


READINGS = [
    Reading("gamesir_nova2", "Controle GameSir", Status.OK, 66),
    Reading("mchose_k7", "Mouse Mchose K7", Status.UNSUPPORTED),
    Reading("mchose_v9", "Headset Mchose V9", Status.NOT_CONNECTED),
]


def test_lowest_percent():
    assert lowest_percent(READINGS) == 66
    assert lowest_percent([Reading("a", "A", Status.ERROR)]) is None
    assert lowest_percent([]) is None


def test_tooltip_limit():
    many = [Reading(f"d{i}", "x" * 30, Status.ERROR) for i in range(10)]
    assert len(tooltip(many)) <= MAX_TOOLTIP


def test_tooltip_snapshot():
    """Protege o texto que o usuário vê. Mudou de propósito? Atualize o snapshot."""
    assert tooltip(READINGS) == SNAP.read_text(encoding="utf-8").rstrip("\n")
