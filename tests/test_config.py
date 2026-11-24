import json

from monitor_bateria.config import MAX_CONFIG_BYTES, Config, load_config, parse_config, write_default_config
from monitor_bateria.devices import GameSirNova2, MchoseK7Ultra


def test_defaults_when_missing(tmp_path):
    cfg = load_config(tmp_path / "nao-existe.json")
    assert (cfg.interval_minutes, cfg.low_battery_percent) == (30, 20)
    assert cfg.interval_seconds == 1800


def test_invalid_json_falls_back(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{isso não é json")
    assert load_config(p) == Config()


def test_oversized_file_is_ignored(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"interval_minutes": 99}) + " " * (MAX_CONFIG_BYTES + 1))
    assert load_config(p) == Config()


def test_values_are_clamped_and_types_checked():
    assert parse_config({"interval_minutes": 1}).interval_minutes == 5
    assert parse_config({"interval_minutes": 99999}).interval_minutes == 1440
    assert parse_config({"interval_minutes": "30"}).interval_minutes == 30
    assert parse_config({"interval_minutes": True}).interval_minutes == 30
    assert parse_config({"low_battery_percent": 1}).low_battery_percent == 5
    assert parse_config([1, 2]) == Config()


def test_device_switches_validated_and_applied():
    cfg = parse_config({"devices": {"mchose_k7": True, "gamesir_nova2": "sim", 5: True, "x": 1}})
    assert cfg.devices == {"mchose_k7": True}
    assert cfg.is_enabled(MchoseK7Ultra) is True
    assert cfg.is_enabled(GameSirNova2) is True      # padrão da classe


def test_write_default_config_does_not_overwrite(tmp_path):
    p = tmp_path / "sub" / "config.json"
    write_default_config(p)
    first = p.read_text()
    p.write_text('{"interval_minutes": 60}')
    write_default_config(p)
    assert p.read_text() != first and json.loads(p.read_text())["interval_minutes"] == 60
