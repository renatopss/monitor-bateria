"""Widget na barra de tarefas (tkinter): desenho do aparelho + número ao lado, e ⚡ se estiver carregando.

Janela sem borda, sempre no topo, que o usuário arrasta até o lugar que quiser (a posição é salva).
Botão direito: menu. Roda numa thread própria; o resto do app só conversa com ela por uma fila.
Único módulo (junto com ui_colors) que importa tkinter. Não é testado sem tela.
"""
from __future__ import annotations

import base64
import gc
import io
import logging
import queue
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable

from .colors import Palette, hex_to_rgba
from .config import load_config, save_widget_pos
from .icon import render_bolt, render_glyph
from .models import Reading, Status
from .single_instance import work_area

log = logging.getLogger(__name__)
GLYPH_HEIGHT = 20
POLL_MS = 200          # olha a fila de pedidos (editar, atualizar, sair) a cada 0,2 s
GAME_CHECK_EVERY = 8   # ... e checa jogo em tela cheia a cada ~1,6 s
MARGIN_RIGHT = 330  # espaço aproximado da bandeja do Windows 11 à direita


def _photo(image) -> tk.PhotoImage:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return tk.PhotoImage(data=base64.b64encode(buffer.getvalue()))


class TaskbarWidget:
    def __init__(
        self,
        config_path: Path,
        kinds: dict[str, str],
        palette: Palette,
        on_refresh: Callable[[], None],
        on_edit_colors: Callable[[], None],
        on_quit: Callable[[], None],
        hide_when: Callable[[], bool] | None = None,
    ) -> None:
        self._config_path = config_path
        self._kinds = kinds
        self._palette = palette
        self._callbacks = (on_refresh, on_edit_colors, on_quit)
        self._hide_when = hide_when
        self._hidden = False
        self._editor_open = False
        self._ticks = 0
        self._on_colors_saved: Callable[[], None] | None = None
        self._queue: queue.Queue = queue.Queue()
        self._readings: list[Reading] = []
        self._thread = threading.Thread(target=self._run, name="widget-barra", daemon=True)

    # ---- chamados de outras threads (só colocam na fila) ------------------
    def start(self) -> None:
        self._thread.start()

    def update(self, readings: list[Reading]) -> None:
        self._queue.put(("readings", list(readings)))

    def set_palette(self, palette: Palette) -> None:
        self._queue.put(("palette", palette))

    def stop(self) -> None:
        self._queue.put(("stop", None))

    def request_edit(self) -> None:
        """Pede (de qualquer thread) para abrir o editor de cores dentro da thread do widget."""
        self._queue.put(("edit", None))

    def set_on_colors_saved(self, callback: Callable[[], None]) -> None:
        self._on_colors_saved = callback

    def join(self, timeout: float = 3.0) -> None:
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout)

    # ---- thread do tkinter -------------------------------------------------
    def _run(self) -> None:
        try:
            self._root = tk.Tk()
            self._build_window()
            self._root.after(POLL_MS, self._poll)
            self._root.mainloop()
        except Exception:  # noqa: BLE001 - o widget nunca derruba o app
            log.exception("falha no widget da barra de tarefas")
        finally:
            self._release_tk()

    def _release_tk(self) -> None:
        """Solta os objetos do tkinter na thread que os criou (evita abortar o processo ao sair)."""
        try:
            self._keep.clear()
        except AttributeError:
            pass
        self._menu = self._frame = None
        self._root = None
        gc.collect()

    def _open_editor(self) -> None:
        if self._editor_open:
            return
        try:
            from .ui_colors import open_color_editor

            self._editor_open = True

            def saved() -> None:
                self._editor_open = False
                if self._on_colors_saved:
                    self._on_colors_saved()

            open_color_editor(self._config_path, self._kinds, saved, parent=self._root)
            self._root.after(500, self._watch_editor)
        except Exception:  # noqa: BLE001
            self._editor_open = False
            log.exception("falha ao abrir o editor de cores")

    def _watch_editor(self) -> None:
        """Libera um novo pedido quando a janela do editor fechar (por Salvar ou Cancelar)."""
        if not any(isinstance(w, tk.Toplevel) for w in self._root.winfo_children()):
            self._editor_open = False
        else:
            self._root.after(500, self._watch_editor)

    def _build_window(self) -> None:
        root = self._root
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=self._palette.colors["bg"])
        self._drag = (0, 0)
        self._menu = tk.Menu(root, tearoff=0)
        refresh, edit, quit_ = self._callbacks
        self._menu.add_command(label="Atualizar agora", command=refresh)
        self._menu.add_command(label="Editar cores…", command=self._open_editor)
        self._menu.add_separator()
        self._menu.add_command(label="Sair", command=quit_)
        self._keep: list[tk.PhotoImage] = []
        self._frame = tk.Frame(root, bg=self._palette.colors["bg"], padx=8)
        self._frame.pack()
        self._bind_all(root)
        self._rebuild()
        self._place(first=True)

    def _bind_all(self, widget) -> None:
        # Só na janela raiz: todo filho já tem a raiz nas bindtags, então ligar
        # também nos filhos fazia o menu (e o arrastar) disparar duas vezes.
        widget.bind("<ButtonPress-1>", self._drag_start)
        widget.bind("<B1-Motion>", self._drag_move)
        widget.bind("<ButtonRelease-1>", self._drag_end)
        widget.bind("<Button-3>", lambda e: self._menu.tk_popup(e.x_root, e.y_root))

    def _rebuild(self) -> None:
        palette, bg = self._palette, self._palette.colors["bg"]
        for child in self._frame.winfo_children():
            child.destroy()
        self._keep.clear()
        by_id = {r.device_id: r for r in self._readings}
        cutout = hex_to_rgba(bg)
        shown = 0
        for device_id, kind in self._kinds.items():
            reading = by_id.get(device_id)
            if reading is None or reading.status is not Status.OK:
                continue  # sem informação útil: não ocupa espaço na barra
            shown += 1
            percent = reading.percent
            glyph = _photo(render_glyph(kind, palette.rgba_for(percent), cutout, GLYPH_HEIGHT))
            self._keep.append(glyph)
            cell = tk.Frame(self._frame, bg=bg, padx=6)
            cell.pack(side="left")
            tk.Label(cell, image=glyph, bg=bg).pack(side="left", padx=(0, 4))
            tk.Label(cell, text=f"{percent}%", bg=bg, fg=palette.colors["text"],
                     font=("Segoe UI", 11, "bold")).pack(side="left")
            if reading.charging:
                bolt = _photo(render_bolt(hex_to_rgba(palette.colors["charge"]), GLYPH_HEIGHT - 2))
                self._keep.append(bolt)
                tk.Label(cell, image=bolt, bg=bg).pack(side="left", padx=(3, 0))
        if not shown:
            # nada a mostrar: fica só um traço pequeno para o menu continuar acessível
            tk.Label(self._frame, text="--", bg=bg, fg=palette.colors["none"],
                     font=("Segoe UI", 11, "bold"), padx=6).pack(side="left")

    def _place(self, first: bool = False) -> None:
        root = self._root
        root.update_idletasks()
        width, height = root.winfo_reqwidth(), root.winfo_reqheight()
        if not first and root.winfo_width() > 1:
            # aparelho entrou/saiu: cresce/encolhe para a esquerda, mantendo a borda direita
            x = root.winfo_x() + root.winfo_width() - width
            root.geometry(f"{width}x{height}+{x}+{root.winfo_y()}")
            return
        saved = load_config(self._config_path).widget_pos
        if saved is not None:
            x, y = saved
        else:
            screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
            area = work_area()
            bar_h = (screen_h - area[3]) if area and screen_h > area[3] else 48
            x = screen_w - width - MARGIN_RIGHT
            y = screen_h - bar_h + max(0, (bar_h - height) // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "stop":
                    self._root.destroy()
                    return
                if kind == "edit":
                    self._open_editor()
                    continue
                if kind == "readings":
                    self._readings = payload
                elif kind == "palette":
                    self._palette = payload
                    self._root.configure(bg=payload.colors["bg"])
                    self._frame.configure(bg=payload.colors["bg"])
                self._rebuild()
                self._place()
        except queue.Empty:
            pass
        self._ticks += 1
        if self._ticks % GAME_CHECK_EVERY == 0:  # a checagem de jogo é mais espaçada que a fila
            self._apply_game_mode()
        self._root.after(POLL_MS, self._poll)

    def _apply_game_mode(self) -> None:
        """Jogo/app em tela cheia: some por completo (não fica por cima, não consome nada)."""
        hide = False
        if self._hide_when is not None:
            try:
                hide = bool(self._hide_when())
            except Exception:  # noqa: BLE001
                hide = False
        if hide and not self._hidden:
            self._root.withdraw()
            self._hidden = True
        elif not hide and self._hidden:
            self._root.deiconify()
            self._root.attributes("-topmost", True)
            self._place()
            self._hidden = False
        if not self._hidden:
            self._root.lift()  # a barra de tarefas também é "topmost": reafirma o nosso lugar

    def _drag_start(self, event) -> None:
        self._drag = (event.x_root - self._root.winfo_x(), event.y_root - self._root.winfo_y())

    def _drag_move(self, event) -> None:
        self._root.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    def _drag_end(self, _event) -> None:
        try:
            save_widget_pos(self._config_path, self._root.winfo_x(), self._root.winfo_y())
        except OSError:
            log.warning("não consegui salvar a posição do widget")
