"""Regenera backend/app/lineas/luna/luna.png desde el CGI Moon Kit de la NASA (dominio publico).

Fuente: https://svs.gsfc.nasa.gov/4720 (albedo LROC + relieve LOLA).
Mezcla 75 % albedo (mares oscuros, tierras altas claras) y 25 % sombreado del relieve
(para que se noten los crateres), en 2048 x 1024 escala de grises.

Uso (desde la raiz del repo, con internet):
  python tools/preparar_luna.py
"""
import io
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
BASE = "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/"
SALIDA = Path(__file__).resolve().parents[1] / "backend/app/lineas/luna/luna.png"
ANCHO = 2048


def bajar(nombre):
    print("descargando", nombre)
    with urllib.request.urlopen(BASE + nombre) as r:
        return Image.open(io.BytesIO(r.read()))


def main():
    w, h = ANCHO, ANCHO // 2
    albedo = np.asarray(bajar("lroc_color_poles_4k.tif").convert("L").resize((w, h), Image.LANCZOS), dtype=float) / 255
    dem = np.asarray(bajar("ldem_16_uint.tif"), dtype=np.float32)
    dem = np.asarray(Image.fromarray(dem).resize((w, h), Image.LANCZOS), dtype=float)

    gy, gx = np.gradient(dem)
    lat = np.deg2rad(90 - (np.arange(h) + 0.5) * 180 / h)[:, None]
    gx = gx / np.maximum(np.cos(lat), 0.05)
    sombra = -(gx * 0.8 + gy * 0.6)                      # luz rasante desde el noroeste
    sombra = np.clip(sombra / (np.percentile(np.abs(sombra), 99) + 1e-9), -1, 1)
    lo, hi = np.percentile(albedo, [1, 99])
    albedo = (albedo - lo) / (hi - lo)
    mezcla = np.clip(0.75 * albedo + 0.25 * (0.5 + 0.5 * sombra), 0, 1)
    Image.fromarray((mezcla * 255).astype(np.uint8)).save(SALIDA, optimize=True)
    print("listo:", SALIDA)


if __name__ == "__main__":
    main()
