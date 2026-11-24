"""Regenera backend/app/lineas/luna_pared/relieve.png: la cara visible de la Luna vista de frente.

Fuente: https://svs.gsfc.nasa.gov/4720 (relieve LOLA ldem_16_uint.tif, dominio publico).
Proyeccion ortografica del hemisferio visible (como se ve desde la Tierra) en un cuadro de
LADO x LADO pixeles. El valor es la altura relativa: se resalta el detalle local (crateres) y se
conserva un poco de la forma grande (mares mas bajos que las tierras altas). Fuera del disco = 0.

Uso (desde la raiz del repo, con internet, o con --dem ruta/local.tif):
  python tools/preparar_luna_pared.py
"""
import argparse
import io
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

Image.MAX_IMAGE_PIXELS = None
URL = "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_16_uint.tif"
SALIDA = Path(__file__).resolve().parents[1] / "backend/app/lineas/luna_pared/relieve.png"
LADO = 1600


def cargar(ruta):
    if ruta:
        return Image.open(ruta)
    print("descargando", URL)
    with urllib.request.urlopen(URL) as r:
        return Image.open(io.BytesIO(r.read()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem")
    a = ap.parse_args()
    dem = np.asarray(cargar(a.dem), dtype=np.float32)
    h, w = dem.shape
    s = (np.arange(LADO) + 0.5) / LADO * 2 - 1
    X, Y = np.meshgrid(s, -s)                      # Y hacia arriba = norte
    r2 = X ** 2 + Y ** 2
    dentro = r2 < 1
    Z = np.sqrt(np.clip(1 - r2, 0, 1))
    lat = np.arcsin(np.clip(Y, -1, 1))
    lon = np.arctan2(X, Z)                         # este a la derecha, como se ve desde la Tierra
    u = (lon / (2 * np.pi) + 0.5) * w - 0.5
    v = (0.5 - lat / np.pi) * h - 0.5
    u0 = np.clip(np.floor(u).astype(int), 0, w - 2)
    v0 = np.clip(np.floor(v).astype(int), 0, h - 2)
    fu, fv = np.clip(u - u0, 0, 1), np.clip(v - v0, 0, 1)
    alt = (dem[v0, u0] * (1 - fu) * (1 - fv) + dem[v0, u0 + 1] * fu * (1 - fv)
           + dem[v0 + 1, u0] * (1 - fu) * fv + dem[v0 + 1, u0 + 1] * fu * fv)
    alt = np.where(dentro, alt, np.median(alt[dentro]))
    grande = gaussian_filter(alt, LADO / 40)
    detalle = alt - grande                         # crateres y bordes
    rel = detalle + 0.35 * (grande - np.median(grande[dentro]))
    lo, hi = np.percentile(rel[dentro], [0.5, 99.5])
    rel = np.clip((rel - lo) / (hi - lo), 0, 1)
    rel = np.where(dentro, 0.02 + 0.98 * rel, 0)
    Image.fromarray((rel * 255).round().astype(np.uint8)).save(SALIDA, optimize=True)
    print("listo:", SALIDA)


if __name__ == "__main__":
    main()
