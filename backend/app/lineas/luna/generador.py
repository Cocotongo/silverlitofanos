"""Generador de lamparas luna: esfera litofano con la superficie de la Luna.

El mapa `luna.png` (2048 x 1024, proyeccion equirectangular, longitud 0 al centro) mezcla el
albedo de LROC con un sombreado del relieve de LOLA, ambos del CGI Moon Kit de la NASA
(dominio publico, https://svs.gsfc.nasa.gov/4720). Se regenera con tools/preparar_luna.py.

Uso:
  python -m app.lineas.luna.generador --diametro 150 --abertura 40 --salida luna.stl --previa previa.png

La esfera es hueca, con una boca abajo para meter la placa LED. Alrededor de la boca hay un
anillo de espesor maximo para que sea rigida, y la boca queda plana para que asiente en la
cama de la impresora (se imprime con la boca hacia abajo).
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from ..litofano.generador import MATERIALES, guardar_stl

MAPA = Path(__file__).with_name("luna.png")


def _mapa():
    return np.asarray(Image.open(MAPA).convert("L"), dtype=np.float64) / 255.0


def _muestrear(mapa, lon, lat):
    """Brillo del mapa (0-1) en longitud/latitud (radianes), interpolacion bilineal."""
    h, w = mapa.shape
    u = ((lon / (2 * np.pi) + 0.5) % 1.0) * w - 0.5
    v = np.clip((0.5 - lat / np.pi) * h - 0.5, 0, h - 1)
    u0 = np.floor(u).astype(int)
    v0 = np.floor(v).astype(int)
    fu, fv = u - u0, v - v0
    u0 %= w
    u1 = (u0 + 1) % w
    v1 = np.minimum(v0 + 1, h - 1)
    arriba = mapa[v0, u0] * (1 - fu) + mapa[v0, u1] * fu
    abajo = mapa[v1, u0] * (1 - fu) + mapa[v1, u1] * fu
    return arriba * (1 - fv) + abajo * fv


def espesores(diametro=150.0, abertura=40.0, material="pla", resolucion=0.5, anillo=6.0,
              t_min=None, t_max=None):
    """Rejilla de espesores (filas = angulo desde el polo norte, columnas = longitud).

    Devuelve (espesor, theta, phi, r_in, alfa0). La fila 0 es la mas cercana al polo norte.
    """
    mat = MATERIALES[material]
    t_min = mat["min"] if t_min is None else t_min
    t_max = mat["max"] if t_max is None else t_max
    r_ext = diametro / 2.0
    r_in = r_ext - t_max
    if not 0 < abertura / 2 < r_in * 0.9:
        raise ValueError("la abertura debe ser menor que el diametro interior")
    alfa0 = np.arcsin(abertura / 2 / r_in)          # angulo de la boca medido desde el polo sur
    theta_max = np.pi - alfa0
    filas = max(8, int(round(theta_max * r_ext / resolucion)))
    cols = max(16, int(round(2 * np.pi * r_ext / resolucion)))
    theta = np.arange(1, filas + 1) * theta_max / filas
    phi = np.arange(cols) * 2 * np.pi / cols
    T, P = np.meshgrid(theta, phi, indexing="ij")
    # longitud 0 (cara visible) hacia -Y, el frente en el slicer; el este queda a la derecha
    brillo = _muestrear(_mapa(), P + np.pi / 2, np.pi / 2 - T)
    esp = t_max - brillo * (t_max - t_min)
    # anillo solido junto a la boca (con transicion suave de 3 mm)
    dist = (theta_max - T) * r_ext
    peso = np.clip((dist - anillo) / 3.0, 0, 1)
    esp = esp * peso + t_max * (1 - peso)
    return esp, theta, phi, r_in, alfa0


def esfera(esp, theta, phi, r_in, alfa0):
    """Malla cerrada de la esfera hueca con boca plana abajo."""
    f, c = esp.shape
    T, P = np.meshgrid(theta, phi, indexing="ij")
    st, ct, cp, sp = np.sin(T), np.cos(T), np.cos(P), np.sin(P)
    inte = np.stack([r_in * st * cp, r_in * st * sp, r_in * ct], -1)
    # la cara exterior termina en el mismo plano que la interior (boca plana): se estiran
    # un poco sus angulos para que ninguna fila quede por debajo de ese plano
    z0 = -r_in * np.cos(alfa0)
    R = r_in + esp
    theta_ext = np.pi - np.arccos(np.clip(-z0 / R.max(), -1, 1))
    Te = T * (theta_ext / theta[-1])
    se, ce = np.sin(Te), np.cos(Te)
    ext = np.stack([R * se * cp, R * se * sp, R * ce], -1)
    rho = np.sqrt(np.maximum(R[-1] ** 2 - z0 ** 2, 0))
    ext[-1] = np.stack([rho * cp[-1], rho * sp[-1], np.full(c, z0)], -1)

    off = f * c
    v = np.concatenate([ext.reshape(-1, 3), inte.reshape(-1, 3),
                        [[0, 0, r_in + esp[0].mean()], [0, 0, r_in]]])
    polo_e, polo_i = 2 * off, 2 * off + 1
    ids = np.arange(off).reshape(f, c)
    ids = np.concatenate([ids, ids[:, :1]], axis=1)
    a, b, cc, d = ids[:-1, :-1], ids[:-1, 1:], ids[1:, 1:], ids[1:, :-1]

    def quads(a, b, cc, d):
        return np.concatenate([np.stack([a, b, cc], -1).reshape(-1, 3),
                               np.stack([a, cc, d], -1).reshape(-1, 3)])

    r0, r1 = ids[0], ids[-1]
    caras = [
        quads(a, d, cc, b),                                    # exterior
        quads(a + off, b + off, cc + off, d + off),            # interior
        np.stack([np.full(c, polo_e), r0[:-1], r0[1:]], -1),   # tapa exterior en el polo
        np.stack([np.full(c, polo_i), r0[1:] + off, r0[:-1] + off], -1),
        quads(r1[:-1], r1[:-1] + off, r1[1:] + off, r1[1:]),   # aro plano de la boca
    ]
    return v, np.concatenate(caras)


def vista_previa(esp, theta, phi, ruta, k=1.2, lado=640):
    """Simula la luna encendida vista de frente (luz en el centro)."""
    s = (np.arange(lado) + 0.5) / lado * 2 - 1
    X, Z = np.meshgrid(s, -s)
    dentro = X ** 2 + Z ** 2 < 1
    Y = -np.sqrt(np.clip(1 - X ** 2 - Z ** 2, 0, 1))  # cara que mira al frente (-Y)
    t = np.arccos(np.clip(Z, -1, 1))
    p = np.arctan2(Y, X) % (2 * np.pi)
    fi = np.clip(np.searchsorted(theta, t), 0, len(theta) - 1)
    ci = np.round(p / (2 * np.pi) * len(phi)).astype(int) % len(phi)
    e = esp[fi, ci]
    luz = np.exp(-k * e) * (0.55 + 0.45 * np.abs(Y))
    luz[t > theta[-1]] = 0
    luz = np.clip(luz / np.percentile(luz[dentro], 99.5), 0, 1)
    calido = np.array([255, 214, 160]) / 255.0
    rgb = np.zeros((lado, lado, 3))
    rgb[dentro] = luz[dentro, None] * calido
    Image.fromarray((rgb * 255).astype(np.uint8)).save(ruta, format="PNG")


def generar(salida_stl, diametro=150.0, abertura=40.0, material="pla", resolucion=0.5, previa=None,
            t_min=None, t_max=None):
    esp, theta, phi, r_in, alfa0 = espesores(diametro, abertura, material, resolucion, t_min=t_min, t_max=t_max)
    v, caras = esfera(esp, theta, phi, r_in, alfa0)
    guardar_stl(salida_stl, v, caras)
    if previa:
        vista_previa(esp, theta, phi, previa, k=MATERIALES[material]["k"])
    tri = v[caras]
    volumen_mm3 = abs(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()) / 6
    densidad = 1.27 if material == "petg" else 1.24
    alto = r_in * np.cos(alfa0) + r_in + esp[0].mean()
    return {"triangulos": int(len(caras)), "medidas": f"Ø{diametro:.0f} x {alto:.0f} mm, boca Ø{abertura:.0f}",
            "gramos": round(volumen_mm3 / 1000 * densidad, 1)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--diametro", type=float, default=150, help="diametro exterior en mm")
    p.add_argument("--abertura", type=float, default=40, help="diametro de la boca para la placa LED, mm")
    p.add_argument("--material", choices=sorted(MATERIALES), default="pla")
    p.add_argument("--resolucion", type=float, default=0.5, help="mm por punto de la malla")
    p.add_argument("--previa", help="guardar PNG simulando la luna encendida")
    p.add_argument("--salida", default="luna.stl")
    a = p.parse_args()
    r = generar(a.salida, a.diametro, a.abertura, a.material, a.resolucion, a.previa)
    print(f"{a.salida}: {r['triangulos']:,} triangulos, {r['medidas']}, ≈ {r['gramos']} g")


if __name__ == "__main__":
    main()
