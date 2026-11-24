"""Ícones da bandeja (pystray). Único módulo que importa pystray; não é testado sem tela.

Modo "separado": um ícone por aparelho (número com contorno na cor do aparelho). Modo "unico": um só,
com a menor bateria. O widget flutuante é opcional e liga/desliga pelo menu, sem reiniciar.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import pystray

from .config import load_config, save_floating_widget
from .icon import render_icon
from .models import Reading, Status
from .service import MonitorService
from .single_instance import fullscreen_app_active, tray_icon_size
from .summary import lowest_percent, tooltip

log = logging.getLogger(__name__)
SINGLE = "__unico__"


def run_tray(service: MonitorService, config_path: Path) -> None:
    config = load_config(config_path)
    state = {"palette": config.palette, "style": config.icon_style, "borders": config.borders,
             "widget": config.widget}
    kinds = {d.device_id: d.icon_kind for d in service.devices}
    names = {d.device_id: d.name for d in service.devices}
    separate = config.tray_mode == "separado" and bool(kinds)
    keys = list(kinds) if separate else [SINGLE]
    stop_event = threading.Event()
    editor_lock = threading.Lock()   # um tkinter por vez: editor avulso OU widget
    widget_lock = threading.Lock()   # serializa ligar/desligar o widget
    icons: dict[str, pystray.Icon] = {}
    widget_box: list = []

    def draw(key: str, readings: list[Reading]):
        palette = state["palette"]
        if key == SINGLE:
            charging = any(r.status is Status.OK and r.charging for r in readings)
            return render_icon(lowest_percent(readings), size=tray_icon_size(), palette=palette,
                               style=state["style"], charging=charging), tooltip(readings)
        mine = next((r for r in readings if r.device_id == key), None)
        percent = mine.percent if mine is not None else None
        charging = bool(mine is not None and mine.status is Status.OK and mine.charging)
        title = mine.short() if mine is not None else names.get(key, key)
        return render_icon(percent, size=tray_icon_size(), kind=kinds[key], palette=palette,
                           style=state["style"], charging=charging,
                           border=state["borders"].get(kinds[key])), title

    def refresh_all() -> None:
        readings = service.latest
        for key, ic in icons.items():
            ic.icon, ic.title = draw(key, readings)
            ic.update_menu()
        for w in widget_box:
            w.update(readings)

    def quit_all() -> None:
        service.stop()
        for w in list(widget_box):
            w.stop()
        for ic in icons.values():
            try:
                ic.stop()
            except Exception:  # noqa: BLE001 - encerrando mesmo assim
                log.exception("falha ao fechar ícone")
        stop_event.set()

    def on_colors_saved() -> None:
        fresh = load_config(config_path)
        state["palette"], state["style"], state["borders"] = fresh.palette, fresh.icon_style, fresh.borders
        for w in widget_box:
            w.set_palette(fresh.palette)
        refresh_all()

    def edit_colors(*_args) -> None:
        if widget_box:  # o editor abre dentro da thread do widget (um só tkinter)
            widget_box[0].request_edit()
            return
        if not editor_lock.acquire(blocking=False):
            return  # já está aberto

        def worker() -> None:
            try:
                from .ui_colors import open_color_editor  # tkinter só aqui, sob demanda
                open_color_editor(config_path, kinds, on_colors_saved)
            except Exception:  # noqa: BLE001 - editor quebrado não pode derrubar a bandeja
                log.exception("falha no editor de cores")
            finally:
                editor_lock.release()

        threading.Thread(target=worker, name="editor-cores", daemon=True).start()

    def start_widget() -> bool:
        if widget_box or not kinds:
            return bool(widget_box)
        if not editor_lock.acquire(blocking=False):
            return False  # editor de cores avulso aberto: dois tkinter em threads diferentes derrubam o app
        editor_lock.release()
        try:
            from .ui_widget import TaskbarWidget  # tkinter só aqui, sob demanda

            widget = TaskbarWidget(
                config_path, kinds, state["palette"],
                on_refresh=service.refresh_now, on_edit_colors=edit_colors, on_quit=quit_all,
                hide_when=fullscreen_app_active if config.game_mode else None,
                on_hide=lambda: toggle_widget(),
            )
            widget.set_on_colors_saved(on_colors_saved)
            widget.update(service.latest)
            widget_box.append(widget)
            widget.start()
            return True
        except Exception:  # noqa: BLE001 - sem tkinter/tela, segue só com a bandeja
            log.exception("widget flutuante indisponível")
            widget_box.clear()
            return False

    def stop_widget() -> None:
        while widget_box:
            w = widget_box.pop()
            w.stop()
            w.join()

    def toggle_widget(*_args) -> None:
        def worker() -> None:
            with widget_lock:
                if widget_box:
                    stop_widget()
                elif not start_widget():
                    first = next(iter(icons.values()), None)
                    if first is not None:
                        first.notify("Feche o editor de cores e tente de novo.", "Widget flutuante")
                    return
                try:
                    save_floating_widget(config_path, bool(widget_box))
                except OSError:
                    log.warning("não consegui salvar a opção do widget")
                for ic in icons.values():
                    ic.update_menu()

        threading.Thread(target=worker, name="widget-toggle", daemon=True).start()

    def menu_items():
        yield from (pystray.MenuItem(r.short(), None, enabled=False) for r in service.latest)
        yield pystray.Menu.SEPARATOR
        yield pystray.MenuItem("Atualizar agora", lambda *_: service.refresh_now())
        yield pystray.MenuItem("Editar cores…", edit_colors)
        yield pystray.MenuItem("Widget flutuante", toggle_widget, checked=lambda _item: bool(widget_box))
        yield pystray.MenuItem("Sair", lambda *_: quit_all())

    ready = []
    for key in keys:
        image, title = draw(key, [])
        ic = pystray.Icon(f"monitor-bateria-{key}", image, title)
        ic.menu = pystray.Menu(menu_items)
        icons[key] = ic

    def on_update(_readings: list[Reading]) -> None:
        refresh_all()

    def on_alert(reading: Reading) -> None:
        ic = icons.get(reading.device_id) or next(iter(icons.values()))
        ic.notify(f"{reading.device_name}: bateria em {reading.percent}%", "Bateria baixa")

    service.set_callbacks(on_update, on_alert)

    for key, ic in icons.items():
        flag = threading.Event()
        ready.append(flag)

        def setup(i: pystray.Icon, flag: threading.Event = flag) -> None:
            i.visible = True
            flag.set()

        ic.run_detached(setup)
    for flag in ready:
        flag.wait(timeout=5)
    if state["widget"]:
        with widget_lock:
            start_widget()
    service.start()
    while not stop_event.wait(timeout=0.5):
        pass
    for w in list(widget_box):
        w.join()  # deixa a thread do tkinter limpar tudo antes do processo terminar
