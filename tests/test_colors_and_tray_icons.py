import json

import pytest

from monitor_bateria.colors import DEFAULT_COLORS, DEFAULT_PALETTE, Palette, clamp_mid, hex_to_rgba, normalize_hex, parse_colors
from monitor_bateria.config import MAX_CONFIG_BYTES, load_config, parse_config, save_colors, write_default_config
from monitor_bateria.devices import ALL_DEVICE_CLASSES
from monitor_bateria.icon import KINDS, render_icon


@pytest.mark.parametrize("v,ok", [("#aabbcc", "#aabbcc"), (" #AABBCC ", "#aabbcc"), ("aabbcc", None), ("#abc", None),
                                  ("#gggggg", None), ("red", None), ("", None), (5, None), (None, None), ("#aabbcc;x", None)])
def test_normalize_hex(v, ok):
    assert normalize_hex(v) == ok


def test_parse_colors_keeps_valid_and_defaults_rest():
    out = parse_colors({"ok": "#112233", "low": "vermelho", "extra": "#000000", "mid": 5})
    assert out["ok"] == "#112233" and out["low"] == DEFAULT_COLORS["low"] and out["mid"] == DEFAULT_COLORS["mid"]
    assert set(out) == set(DEFAULT_COLORS)
    assert parse_colors("lixo") == DEFAULT_COLORS


def test_palette_thresholds():
    p = Palette(dict(DEFAULT_COLORS), low_percent=20, mid_percent=50)
    assert [p.hex_for(x) for x in (None, 0, 20, 21, 50, 51, 100)] == [
        DEFAULT_COLORS["none"], DEFAULT_COLORS["low"], DEFAULT_COLORS["low"], DEFAULT_COLORS["mid"],
        DEFAULT_COLORS["mid"], DEFAULT_COLORS["ok"], DEFAULT_COLORS["ok"]]
    assert hex_to_rgba("#010203") == (1, 2, 3, 255)
    with pytest.raises(ValueError):
        hex_to_rgba("azul")


def test_mid_is_always_above_low():
    assert clamp_mid(10, 30) == 35 and clamp_mid(500, 20) == 90 and clamp_mid(50, 20) == 50
    assert parse_config({"low_battery_percent": 40, "mid_percent": 10}).palette.mid_percent == 45


def test_config_defaults_and_validation():
    cfg = parse_config({"tray_mode": "bagunca", "colors": {"ok": "#00ff00"}})
    assert cfg.tray_mode == "separado" and cfg.colors["ok"] == "#00ff00"
    assert parse_config({"tray_mode": "unico"}).tray_mode == "unico"
    assert parse_config({}).colors == DEFAULT_COLORS


def test_save_colors_preserves_other_settings_and_validates(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"interval_minutes": 60, "devices": {"mchose_k7": True}}))
    save_colors(p, {"ok": "#123456", "low": "lixo"}, 70)
    data = json.loads(p.read_text())
    assert data["interval_minutes"] == 60 and data["devices"] == {"mchose_k7": True}
    assert data["colors"]["ok"] == "#123456" and data["colors"]["low"] == DEFAULT_COLORS["low"]
    assert data["mid_percent"] == 70
    assert load_config(p).palette.colors["ok"] == "#123456"
    assert not list(tmp_path.glob(".config-*"))  # sem sobras do arquivo temporário


def test_save_colors_survives_corrupt_or_huge_file(tmp_path):
    p = tmp_path / "config.json"
    p.write_text("{quebrado")
    save_colors(p, DEFAULT_COLORS, 50)
    assert json.loads(p.read_text())["mid_percent"] == 50
    p.write_text(json.dumps({"interval_minutes": 5}) + " " * (MAX_CONFIG_BYTES + 1))
    save_colors(p, DEFAULT_COLORS, 50)
    assert "interval_minutes" not in json.loads(p.read_text())  # arquivo grande demais é descartado


def test_default_config_includes_colors(tmp_path):
    p = tmp_path / "c.json"
    write_default_config(p)
    assert json.loads(p.read_text())["colors"] == DEFAULT_COLORS


@pytest.mark.parametrize("kind", [None, *KINDS])
@pytest.mark.parametrize("pct", [None, 0, 5, 66, 100])
@pytest.mark.parametrize("size", [16, 32, 64])
def test_every_icon_renders(kind, pct, size):
    img = render_icon(pct, size=size, kind=kind)
    assert img.size == (size, size) and img.mode == "RGBA"


def test_icon_uses_custom_palette():
    pal = Palette({**DEFAULT_COLORS, "ok": "#0000ff"})
    assert render_icon(90, palette=pal).getpixel((3, 32))[:3] == (0, 0, 255)


def test_unknown_kind_falls_back_to_number_only():
    assert render_icon(50, kind="geladeira").size == (64, 64)


@pytest.mark.parametrize("cls", ALL_DEVICE_CLASSES, ids=lambda c: c.device_id)
def test_every_device_has_an_icon_kind(cls):
    assert cls.icon_kind in KINDS


@pytest.mark.parametrize("pct", [None, 0, 7, 66, 100])
@pytest.mark.parametrize("size", [16, 32, 64])
def test_big_style_renders(pct, size):
    img = render_icon(pct, size=size, kind="mouse", style="grande")
    assert img.size == (size, size)


def test_big_style_fills_more_of_the_icon_than_the_default():
    def ink(img):
        fg = (255, 255, 255, 255)
        raw = img.convert("RGBA").tobytes()
        return sum(1 for i in range(0, len(raw), 4) if raw[i:i + 4] == bytes(fg))
    assert ink(render_icon(66, kind="mouse", style="grande")) > ink(render_icon(66, kind="mouse"))


def test_icon_style_config_and_save(tmp_path):
    assert parse_config({}).icon_style == "grande"
    assert parse_config({"icon_style": "grande"}).icon_style == "grande"
    assert parse_config({"icon_style": "xyz"}).icon_style == "grande"
    p = tmp_path / "c.json"
    save_colors(p, DEFAULT_COLORS, 50, "grande")
    assert load_config(p).icon_style == "grande"
    save_colors(p, DEFAULT_COLORS, 50, "lixo")           # inválido: mantém o anterior
    assert load_config(p).icon_style == "grande"


@pytest.mark.parametrize("kind", [None, *KINDS])
@pytest.mark.parametrize("pct", [None, 0, 66, 100])
def test_side_style_renders_even_without_kind(kind, pct):
    assert render_icon(pct, size=24, kind=kind, style="lado").size == (24, 24)


def test_side_style_is_valid_in_config():
    assert parse_config({"icon_style": "lado"}).icon_style == "lado"


from monitor_bateria.icon import render_bolt  # noqa: E402


@pytest.mark.parametrize("style", ["completo", "lado", "grande"])
@pytest.mark.parametrize("kind", [None, *KINDS])
@pytest.mark.parametrize("size", [16, 24, 32, 64])
def test_charging_bolt_renders_in_every_style(style, kind, size):
    assert render_icon(93, size=size, kind=kind, style=style, charging=True).size == (size, size)


def test_charging_bolt_is_drawn_and_uses_the_palette_color():
    plain = render_icon(93, size=64, kind="mouse", style="grande")
    bolt = render_icon(93, size=64, kind="mouse", style="grande", charging=True)
    assert plain.tobytes() != bolt.tobytes()
    pal = Palette({**DEFAULT_COLORS, "charge": "#ff00ff"})
    assert (255, 0, 255, 255) in set(render_icon(93, kind="mouse", style="grande", charging=True, palette=pal).getdata())


def test_bolt_glyph():
    b = render_bolt((255, 212, 0, 255), 20)
    assert b.height == 20 and b.mode == "RGBA"
