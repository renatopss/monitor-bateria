"""Gera o ícone do executável/instalador (bateria verde) em packaging/build/app.ico."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((20, 64, 216, 192), radius=22, outline=(235, 235, 235, 255), width=16)
d.rounded_rectangle((216, 102, 244, 154), radius=8, fill=(235, 235, 235, 255))
d.rounded_rectangle((44, 88, 192, 168), radius=10, fill=(46, 204, 113, 255))
d.polygon([(128, 76), (92, 134), (122, 134), (110, 180), (152, 118), (122, 118), (136, 76)],
          fill=(255, 255, 255, 255))
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
