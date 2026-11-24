"""Ponto de entrada: python -m monitor_bateria [--once]"""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys

from . import __version__
from .config import config_dir, load_config, write_default_config
from .devices import ALL_DEVICE_CLASSES
from .service import MonitorService
from .single_instance import acquire_single_instance, enable_dpi_awareness, fullscreen_app_active, lower_priority
from .transport import real_transport_factory


def _setup_logging() -> None:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        directory / "monitor.log", maxBytes=200_000, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="monitor_bateria")
    parser.add_argument("--once", action="store_true", help="lê uma vez, imprime e sai (sem bandeja)")
    parser.add_argument("--cores", action="store_true", help="abre só o editor de cores")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    _setup_logging()
    config_path = config_dir() / "config.json"
    write_default_config(config_path)
    config = load_config(config_path)

    devices = [
        cls(real_transport_factory) for cls in ALL_DEVICE_CLASSES if config.is_enabled(cls)
    ]
    service = MonitorService(
        devices,
        interval_s=config.interval_seconds,
        low_percent=config.low_battery_percent,
        pause_when=fullscreen_app_active if config.game_mode and not args.once else None,
    )

    enable_dpi_awareness()  # antes de criar qualquer janela/ícone
    lower_priority()

    if args.cores:
        from .ui_colors import open_color_editor  # importação tardia: exige tkinter/tela

        open_color_editor(
            config_path, {c.device_id: c.icon_kind for c in ALL_DEVICE_CLASSES if config.is_enabled(c)}
        )
        return 0

    if args.once:
        for reading in service.poll_once():
            print(reading.short())
        return 0

    if not acquire_single_instance():
        logging.getLogger(__name__).info("já existe uma instância rodando")
        return 0

    from .tray import run_tray  # importação tardia: exige ambiente gráfico

    run_tray(service, config_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
