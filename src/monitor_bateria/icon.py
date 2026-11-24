"""Desenha os ícones da bandeja (pictograma do aparelho + número) com Pillow."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .colors import DEFAULT_PALETTE, Palette, hex_to_rgba

GRAY = DEFAULT_PALETTE.rgba_for(None)
RED = DEFAULT_PALETTE.rgba_for(0)
AMBER = DEFAULT_PALETTE.rgba_for(40)
GREEN = DEFAULT_PALETTE.rgba_for(100)

KINDS = ("controller", "mouse", "headset")


def color_for(percent: int | None, palette: Palette = DEFAULT_PALETTE) -> tuple[int, int, int, int]:
    return palette.rgba_for(percent)


BOLD_FONTS = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")


def _font(size: int, bold: bool = False):
    if bold:
        for name in BOLD_FONTS:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except (TypeError, OSError):  # Pillow antigo ou sem FreeType
        return ImageFont.load_default()


def _draw_pictogram(draw: ImageDraw.ImageDraw, kind: str, fg, bg) -> None:
    """Desenha no canvas de 64x64, na faixa de cima (y de 4 a 30)."""
    if kind == "controller":
        draw.rounded_rectangle([10, 9, 54, 27], radius=9, fill=fg)
        draw.rectangle([17, 16, 25, 19], fill=bg)          # cruzeta
        draw.rectangle([19, 13, 22, 22], fill=bg)
        draw.ellipse([40, 13, 45, 18], fill=bg)            # botões
        draw.ellipse([46, 18, 51, 23], fill=bg)
    elif kind == "mouse":
        draw.rounded_rectangle([23, 4, 41, 30], radius=9, fill=fg)
        draw.line([32, 4, 32, 15], fill=bg, width=2)       # divisão dos botões
        draw.line([23, 15, 41, 15], fill=bg, width=2)
    elif kind == "headset":
        draw.arc([13, 3, 51, 37], start=180, end=360, fill=fg, width=4)
        draw.rounded_rectangle([9, 16, 19, 29], radius=3, fill=fg)
        draw.rounded_rectangle([45, 16, 55, 29], radius=3, fill=fg)


BOLT_POINTS = [(38, 0), (10, 36), (28, 36), (22, 64), (54, 24), (35, 24), (46, 0)]


def render_bolt(color: tuple[int, int, int, int], height: int = 24) -> Image.Image:
    """Raio de 'carregando', desenhado (não depende de fonte), com contorno escuro para destacar."""
    canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).polygon(BOLT_POINTS, fill=color, outline=(0, 0, 0, 255), width=3)
    box = canvas.getbbox() or (0, 0, 64, 64)
    bolt = canvas.crop(box)
    width = max(1, round(bolt.width * height / bolt.height))
    return bolt.resize((width, height), Image.LANCZOS)


def render_icon(
    percent: int | None,
    size: int = 64,
    kind: str | None = None,
    palette: Palette = DEFAULT_PALETTE,
    style: str = "completo",
    charging: bool = False,
) -> Image.Image:
    """`kind` None = só o número (ícone único); com `kind`, desenho em cima e número embaixo.
    style="lado": desenho à esquerda e número à direita. style="grande": ignora o desenho e usa o número enorme, em negrito, ocupando o ícone todo."""
    scale = 64
    image = Image.new("RGBA", (scale, scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    bg, fg = palette.rgba_for(percent), palette.text_rgba()
    big = style == "grande"
    side = style == "lado" and kind in KINDS
    draw.rounded_rectangle([0, 0, scale - 1, scale - 1], radius=scale // (10 if big else 6), fill=bg)
    text = "?" if percent is None else str(percent)
    if side:
        glyph = Image.new("RGBA", (scale, scale), (0, 0, 0, 0))
        _draw_pictogram(ImageDraw.Draw(glyph), kind, fg, bg)
        box = glyph.getbbox()
        if box:
            glyph = glyph.crop(box)
            width = 24
            glyph = glyph.resize((width, max(1, round(glyph.height * width / glyph.width))), Image.LANCZOS)
            image.alpha_composite(glyph, (3, (scale - glyph.height) // 2))
        font_size, center_y = int(scale * 0.7), scale // 2
    elif big:
        font_size, center_y = int(scale * (0.92 if len(text) < 3 else 0.68)), scale // 2
    elif kind in KINDS:
        _draw_pictogram(draw, kind, fg, bg)
        font_size, center_y = int(scale * (0.40 if len(text) < 3 else 0.32)), 47
    else:
        font_size, center_y = int(scale * (0.62 if len(text) < 3 else 0.46)), scale // 2
    font = _font(font_size, bold=big or side)
    if big or side:  # encolhe até o número caber inteiro na área, qualquer que seja a fonte
        max_w = (scale - 30) if side else (scale - 6)
        while font_size > 8:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            if right - left <= max_w and bottom - top <= scale - 6:
                break
            font_size -= 2
            font = _font(font_size, bold=True)
    text_x = (28 + (scale - 28) / 2 - 1) if side else scale / 2
    try:
        draw.text((text_x, center_y), text, fill=fg, font=font, anchor="mm")
    except ValueError:  # fonte bitmap não aceita âncora
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        draw.text((text_x - (right - left) / 2, center_y - (bottom - top) / 2), text, fill=fg, font=font)
    if charging:  # raio no canto superior direito
        bolt = render_bolt(hex_to_rgba(palette.colors["charge"]), int(scale * 0.5))
        image.alpha_composite(bolt, (scale - bolt.width - 1, 1))
    return image if size == scale else image.resize((size, size), Image.LANCZOS)


def render_glyph(kind: str, color: tuple[int, int, int, int], cutout: tuple[int, int, int, int], height: int = 24) -> Image.Image:
    """Só o desenho do aparelho (sem fundo), na cor dada, para o widget da barra de tarefas."""
    canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    if kind in KINDS:
        _draw_pictogram(ImageDraw.Draw(canvas), kind, color, cutout)
    box = canvas.getbbox() or (0, 0, 64, 64)
    glyph = canvas.crop(box)
    width = max(1, round(glyph.width * height / glyph.height))
    return glyph.resize((width, height), Image.LANCZOS)
