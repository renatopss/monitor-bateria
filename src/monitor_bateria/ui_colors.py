"""Editor de cores (tkinter). Único módulo que importa tkinter. Janela simples:
escolhe as cores, o limite de 'média', vê o resultado em cada aparelho e salva no config.json.
Não é testado sem tela; a lógica (validação/gravação) fica em colors.py e config.py."""
from __future__ import annotations

import base64
import gc
import io
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, messagebox
from typing import Callable

from .colors import (
    BORDER_LABELS, COLOR_LABELS, DEFAULT_BORDERS, DEFAULT_COLORS, DEFAULT_MID_PERCENT, Palette, clamp_mid,
    normalize_hex, parse_border,
)
from .config import load_config, save_colors
from .icon import render_icon

SAMPLES = (95, 45, 15, None)  # exemplos mostrados na prévia
KIND_TITLES = {"controller": "Controle", "mouse": "Mouse", "headset": "Headset"}


def _photo(image) -> tk.PhotoImage:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return tk.PhotoImage(data=base64.b64encode(buffer.getvalue()))


def open_color_editor(
    config_path: Path,
    kinds: dict[str, str],
    on_saved: Callable[[], None] | None = None,
    parent: tk.Misc | None = None,
) -> None:
    """Sem `parent`: cria a própria janela e bloqueia até fechar (uso avulso, --cores).
    Com `parent` (o widget): abre como janela filha na MESMA thread/interpretador do tkinter e
    volta na hora, sem segundo Tk em outra thread (isso derrubava o processo)."""
    config = load_config(config_path)
    root = tk.Toplevel(parent) if parent is not None else tk.Tk()
    root.title("Monitor de bateria — cores")
    root.resizable(False, False)

    hex_vars = {k: tk.StringVar(value=v) for k, v in config.colors.items()}
    mid_var = tk.IntVar(value=clamp_mid(config.mid_percent, config.low_battery_percent))
    style_var = tk.StringVar(value=config.icon_style)
    border_vars = {k: tk.StringVar(value=", ".join(config.borders.get(k, []))) for k in BORDER_LABELS}
    swatches: dict[str, tk.Label] = {}
    previews: list[tuple[tk.Label, str, int | None]] = []
    keep: list[tk.PhotoImage] = []  # tk perde imagens sem referência

    def current_palette() -> Palette:
        colors = {}
        for key, var in hex_vars.items():
            colors[key] = normalize_hex(var.get()) or DEFAULT_COLORS[key]
        try:
            mid = int(mid_var.get())
        except (tk.TclError, ValueError):
            mid = DEFAULT_MID_PERCENT
        return Palette(colors, config.low_battery_percent, clamp_mid(mid, config.low_battery_percent))

    def current_borders() -> dict[str, list[str]]:
        out = {}
        for kind, var in border_vars.items():
            valid = parse_border(var.get())
            out[kind] = valid if valid is not None else list(DEFAULT_BORDERS[kind])
        return out

    def redraw(*_a) -> None:
        palette = current_palette()
        borders = current_borders()
        keep.clear()
        for key, label in swatches.items():
            label.configure(bg=palette.colors[key])
        for label, kind, pct in previews:
            photo = _photo(render_icon(pct, size=48, kind=kind or None, palette=palette, style=style_var.get(),
                                       border=borders.get(kind)))
            keep.append(photo)
            label.configure(image=photo)

    def pick(key: str) -> None:
        chosen = colorchooser.askcolor(color=current_palette().colors[key], parent=root)[1]
        if chosen and normalize_hex(chosen):
            hex_vars[key].set(normalize_hex(chosen))
            redraw()

    frame = tk.Frame(root, padx=14, pady=12)
    frame.pack()
    tk.Label(frame, text="Cores dos ícones", font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
    for i, key in enumerate(COLOR_LABELS, start=1):
        tk.Label(frame, text=COLOR_LABELS[key]).grid(row=i, column=0, sticky="w", pady=2)
        swatch = tk.Label(frame, width=4, relief="solid", bd=1, bg=hex_vars[key].get())
        swatch.grid(row=i, column=1, padx=8)
        swatch.bind("<Button-1>", lambda _e, k=key: pick(k))
        swatches[key] = swatch
        entry = tk.Entry(frame, textvariable=hex_vars[key], width=9)
        entry.grid(row=i, column=2)
        entry.bind("<KeyRelease>", redraw)
    row = len(COLOR_LABELS) + 1
    for kind, label in BORDER_LABELS.items():
        tk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
        entry = tk.Entry(frame, textvariable=border_vars[kind], width=20)
        entry.grid(row=row, column=1, columnspan=2, sticky="w", padx=8)
        entry.bind("<KeyRelease>", redraw)
        row += 1
    tk.Label(frame, text="Contorno: cores de fora para dentro, separadas por vírgula (vazio = sem contorno).",
             fg="#555").grid(row=row, column=0, columnspan=3, sticky="w")
    row += 1
    tk.Label(frame, text="“Média” vale até (%)").grid(row=row, column=0, sticky="w", pady=(8, 2))
    spin = tk.Spinbox(frame, from_=10, to=90, width=5, textvariable=mid_var, command=redraw)
    spin.grid(row=row, column=2, sticky="w", pady=(8, 2))
    spin.bind("<KeyRelease>", redraw)
    tk.Label(frame, text="Estilo do ícone").grid(row=row + 5, column=0, sticky="w", pady=(6, 0))
    for j, (value, label) in enumerate((("completo", "Desenho em cima"), ("lado", "Desenho ao lado"), ("grande", "Só número grande"))):
        tk.Radiobutton(frame, text=label, value=value, variable=style_var, command=redraw).grid(
            row=row + 5 + j, column=1, columnspan=2, sticky="w", pady=(6 if j == 0 else 0, 0))
    tk.Label(frame, text=f"“Baixa” vale até {config.low_battery_percent}% (alerta). Clique no quadrado para escolher a cor.",
             fg="#555").grid(row=row + 1, column=0, columnspan=3, sticky="w")

    tk.Label(frame, text="Prévia", font=("Segoe UI", 11, "bold")).grid(
        row=row + 2, column=0, columnspan=3, sticky="w", pady=(10, 4))
    grid = tk.Frame(frame)
    grid.grid(row=row + 3, column=0, columnspan=3)
    shown = [k for k in dict.fromkeys(kinds.values()) if k] or ["controller", "mouse", "headset"]
    for r, kind in enumerate(shown):
        tk.Label(grid, text=KIND_TITLES.get(kind, kind), width=9, anchor="w").grid(row=r, column=0)
        for c, pct in enumerate(SAMPLES, start=1):
            lab = tk.Label(grid)
            lab.grid(row=r, column=c, padx=3, pady=3)
            previews.append((lab, kind, pct))

    def save() -> None:
        palette = current_palette()
        bad = [COLOR_LABELS[k] for k, v in hex_vars.items() if not normalize_hex(v.get())]
        bad += [BORDER_LABELS[k] for k, v in border_vars.items() if parse_border(v.get()) is None]
        if bad:
            messagebox.showerror("Cor inválida", "Use o formato #rrggbb em: " + ", ".join(bad), parent=root)
            return
        try:
            save_colors(config_path, palette.colors, palette.mid_percent, style_var.get(), current_borders())
        except OSError:
            messagebox.showerror("Erro", "Não consegui salvar o config.json.", parent=root)
            return
        if on_saved:
            on_saved()
        root.destroy()

    def restore() -> None:
        for key, value in DEFAULT_COLORS.items():
            hex_vars[key].set(value)
        mid_var.set(DEFAULT_MID_PERCENT)
        for kind, rings in DEFAULT_BORDERS.items():
            border_vars[kind].set(", ".join(rings))
        style_var.set("grande")
        redraw()

    buttons = tk.Frame(frame)
    buttons.grid(row=row + 8, column=0, columnspan=3, sticky="e", pady=(10, 0))
    tk.Button(buttons, text="Restaurar padrão", command=restore).pack(side="left", padx=4)
    tk.Button(buttons, text="Cancelar", command=root.destroy).pack(side="left", padx=4)
    tk.Button(buttons, text="Salvar", command=save, default="active").pack(side="left", padx=4)

    def cleanup() -> None:
        """Solta tudo do tkinter AQUI, na thread dona dele (senão o processo pode abortar ao sair)."""
        previews.clear()
        swatches.clear()
        keep.clear()
        hex_vars.clear()
        border_vars.clear()

    redraw()
    if parent is not None:
        root.bind("<Destroy>", lambda e: cleanup() if e.widget is root else None)
        root.lift()
        root.focus_force()
        return
    root.mainloop()
    cleanup()
    del root
    gc.collect()
