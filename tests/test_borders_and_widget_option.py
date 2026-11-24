"""Contorno colorido por aparelho na bandeja e widget flutuante opcional."""
import json

import pytest

from monitor_bateria.colors import DEFAULT_BORDERS, DEFAULT_COLORS, hex_to_rgba, parse_border, parse_borders
from monitor_bateria.config import load_config, parse_config, save_colors, save_floating_widget, write_default_config
from monitor_bateria.devices import ALL_DEVICE_CLASSES
from monitor_bateria.icon import KINDS, render_icon


def test_default_borders_match_each_device():
    assert DEFAULT_BORDERS["controller"] == ["#9e9e9e"]              # controle: cinza
    assert set(DEFAULT_BORDERS["mouse"]) == {"#000000", "#d4af37"}    # mouse: preto e dourado
    assert set(DEFAULT_BORDERS["headset"]) == {"#000000", "#e53935"}  # headset: preto e vermelho
    assert set(DEFAULT_BORDERS) == set(KINDS)


@pytest.mark.parametrize("raw,out", [
    (["#AABBCC"], ["#aabbcc"]), ("#111111, #222222", ["#111111", "#222222"]), ("", []), ([], []),
    ("#111111;#222222", ["#111111", "#222222"]),
    (["#111111", "lixo"], None), ("vermelho", None), (5, None), (None, None),
    (["#111111"] * 4, None),  # mais de 3 anéis
])
def test_parse_border(raw, out):
    assert parse_border(raw) == out


def test_parse_borders_keeps_valid_and_defaults_rest():
    out = parse_borders({"mouse": ["#010101"], "headset": "lixo", "geladeira": ["#000000"]})
    assert out["mouse"] == ["#010101"] and out["headset"] == DEFAULT_BORDERS["headset"]
    assert set(out) == set(DEFAULT_BORDERS)
    assert parse_borders("lixo") == DEFAULT_BORDERS


def test_widget_is_off_by_default_and_old_key_does_not_turn_it_on():
    assert parse_config({}).widget is False
    assert parse_config({"widget": True}).widget is False  # config gravado pela 0.0.1
    assert parse_config({"floating_widget": True}).widget is True
    assert parse_config({"floating_widget": "sim"}).widget is False


def test_save_floating_widget_preserves_rest(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"interval_minutes": 60}))
    save_floating_widget(p, True)
    assert load_config(p).widget is True and load_config(p).interval_minutes == 60
    save_floating_widget(p, False)
    assert load_config(p).widget is False


def test_default_config_has_borders_and_widget_off(tmp_path):
    p = tmp_path / "c.json"
    write_default_config(p)
    data = json.loads(p.read_text())
    assert data["borders"] == DEFAULT_BORDERS and data["floating_widget"] is False
    assert load_config(p).borders == DEFAULT_BORDERS


def test_save_colors_writes_borders_and_keeps_them_when_omitted(tmp_path):
    p = tmp_path / "c.json"
    save_colors(p, DEFAULT_COLORS, 50, "grande", {"mouse": ["#123456"], "headset": ["lixo"], "controller": []})
    cfg = load_config(p)
    assert cfg.borders["mouse"] == ["#123456"] and cfg.borders["controller"] == []
    assert cfg.borders["headset"] == DEFAULT_BORDERS["headset"]
    save_colors(p, DEFAULT_COLORS, 50)  # sem borders: não mexe
    assert load_config(p).borders["mouse"] == ["#123456"]


@pytest.mark.parametrize("kind", KINDS)
def test_icon_draws_the_device_border_outside_in(kind):
    rings = DEFAULT_BORDERS[kind]
    img = render_icon(80, size=64, kind=kind, style="grande", border=rings)
    assert img.getpixel((32, 2)) == hex_to_rgba(rings[0])          # anel de fora
    if len(rings) > 1:
        assert img.getpixel((32, 7)) == hex_to_rgba(rings[1])      # anel de dentro
    assert img.getpixel((14, 14)) == hex_to_rgba(DEFAULT_COLORS["ok"])  # miolo = cor da bateria


def test_no_border_keeps_old_look():
    assert render_icon(80, kind="mouse", border=None).tobytes() == render_icon(80, kind="mouse", border=[]).tobytes()


@pytest.mark.parametrize("style", ["completo", "lado", "grande"])
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("pct", [None, 5, 66, 100])
@pytest.mark.parametrize("size", [16, 20, 24, 32, 64])
def test_bordered_icons_render_everywhere(style, kind, pct, size):
    img = render_icon(pct, size=size, kind=kind, style=style, border=DEFAULT_BORDERS[kind], charging=pct == 66)
    assert img.size == (size, size)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("pct", [5, 66, 100])
def test_big_number_stays_inside_the_border(kind, pct):
    """Nenhum pixel do número (branco) pode cair em cima do contorno."""
    img = render_icon(pct, size=64, kind=kind, style="grande", border=DEFAULT_BORDERS[kind])
    inset = 8 if len(DEFAULT_BORDERS[kind]) == 1 else 10
    white = (255, 255, 255, 255)
    for x in range(64):
        for y in range(64):
            if x < inset or y < inset or x >= 64 - inset or y >= 64 - inset:
                assert img.getpixel((x, y)) != white, (x, y)


@pytest.mark.parametrize("cls", ALL_DEVICE_CLASSES, ids=lambda c: c.device_id)
def test_every_device_has_a_default_border(cls):
    assert DEFAULT_BORDERS[cls.icon_kind]
