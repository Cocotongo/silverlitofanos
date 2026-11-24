"""Generador del cubo de 4 fotos: 4 paneles litofano con cantos a 45 grados, base y tapa.

Cada cara es un panel con la cara de afuera PLANA y el relieve hacia adentro (hacia la luz).
Los cantos laterales van a 45 grados, asi las 4 caras embonan en las esquinas sin que se vea
la union. Los cantos de arriba y abajo entran en una ranura de la base y de la tapa.

Piezas (un STL cada una):
  cara1..cara4  se imprimen de pie, con la cara plana hacia el frente y brim
  base          caja con ranura arriba, hueco para la tira LED y salida para el cable
  tapa          tapa con la misma ranura por abajo

Uso:
  python -m app.lineas.cubo.generador f1.jpg f2.jpg f3.jpg f4.jpg --lado 80 --salida cubo/
"""
import argparse
from pathlib import Path

import numpy as np
from manifold3d import Manifold
from PIL import Image

from ..litofano.generador import MATERIALES, cargar_espesores, guardar_stl, malla_cerrada, vista_previa


def medidas(lado=80.0, material="pla"):
    """Medidas de construccion (mm) que dependen del lado del cubo y del material."""
    t_max = MATERIALES[material]["max"]
    grueso = t_max + 1.0              # espesor del marco (como en el panel clasico)
    return {
        "lado": lado,                 # ancho exterior de cada cara (y alto del panel)
        "grueso": grueso,
        "marco_lado": grueso + 2.0,   # marco a los lados: incluye el canto a 45
        "marco_borde": 6.0,           # marco arriba y abajo: entra en la ranura
        "ranura": 4.0,                # profundidad de la ranura en base y tapa
        "holgura": 0.3,               # juego de la ranura por lado
        "pared": 4.0,                 # pared de la base y la tapa alrededor de la ranura
        "alto_base": 28.0,            # espacio para la tira LED y el cable
        "piso": 2.0,
        "tapa": 6.0,
        "cable": (10.0, 7.0),         # ancho x alto de la salida del cable
    }


def espesores_cara(foto, m, material="pla", resolucion=0.2, encuadre=(0.5, 0.5, 1.0), mejorar=True):
    """Mapa de espesores de una cara: foto al centro y marco solido alrededor."""
    mat = MATERIALES[material]
    ancho_img = m["lado"] - 2 * m["marco_lado"]
    alto_img = m["lado"] - 2 * m["marco_borde"]
    cols, filas = int(round(ancho_img / resolucion)), int(round(alto_img / resolucion))
    esp = cargar_espesores(foto, cols, filas, mat["min"], mat["max"], encuadre=encuadre, mejorar=mejorar)
    nl, nb = int(round(m["marco_lado"] / resolucion)), int(round(m["marco_borde"] / resolucion))
    return np.pad(esp, ((nb, nb), (nl, nl)), constant_values=m["grueso"])


def cara(esp, m):
    """Malla de una cara. Afuera (y=0) plano; el relieve crece hacia +y (adentro).

    La cara de adentro se encoge de forma lineal para que los cantos laterales queden a 45
    grados: afuera mide `lado` y adentro `lado - 2*grueso`.
    """
    f, c = esp.shape
    L, g = m["lado"], m["grueso"]
    x = np.linspace(0, L, c)
    z = np.linspace(0, L, f)
    X, Z = np.meshgrid(x, z)
    afuera = np.stack([X, np.zeros_like(X), Z], -1)
    adentro = np.stack([g + X * (L - 2 * g) / L, esp, Z], -1)
    return malla_cerrada(afuera, adentro, cerrar_columnas=False)


def _caja(x0, y0, z0, x1, y1, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def _marco(exterior, interior, z0, z1):
    """Anillo cuadrado centrado en el origen."""
    e, i = exterior / 2, interior / 2
    return _caja(-e, -e, z0, e, e, z1) - _caja(-i, -i, z0 - 1, i, i, z1 + 1)


def base(m):
    L, g, h, r = m["lado"], m["grueso"], m["holgura"], m["ranura"]
    afuera = L + 2 * h + 2 * m["pared"]
    alto = m["alto_base"]
    cuerpo = _caja(-afuera / 2, -afuera / 2, 0, afuera / 2, afuera / 2, alto)
    ranura = _marco(L + 2 * h, L - 2 * g - 2 * h, alto - r, alto + 1)
    hueco_luz = L - 2 * g - 2 * h - 2 * m["pared"]          # deja un borde interior de una pared
    hueco = _caja(-hueco_luz / 2, -hueco_luz / 2, m["piso"], hueco_luz / 2, hueco_luz / 2, alto + 1)
    # camara hueca bajo la ranura (paredes de 2.4 mm) para ahorrar material
    c = afuera / 2 - 2.4
    camara = _caja(-c, -c, m["piso"], c, c, alto - r - 2.0)
    cw, ch = m["cable"]
    cable = _caja(-cw / 2, -afuera, m["piso"], cw / 2, 0, m["piso"] + ch)
    return cuerpo - ranura - hueco - camara - cable


def tapa(m):
    L, g, h, r = m["lado"], m["grueso"], m["holgura"], m["ranura"]
    afuera = L + 2 * h + 2 * m["pared"]
    cuerpo = _caja(-afuera / 2, -afuera / 2, 0, afuera / 2, afuera / 2, m["tapa"])
    ranura = _marco(L + 2 * h, L - 2 * g - 2 * h, -1, r)           # por abajo (se imprime volteada)
    i = (L - 2 * g - 2 * h) / 2 - m["pared"]                         # hueco interior: deja 2 mm de techo
    hueco = _caja(-i, -i, -1, i, i, m["tapa"] - 2.0)
    return cuerpo - ranura - hueco


def guardar_manifold(ruta, pieza: Manifold):
    malla = pieza.to_mesh()
    v = np.asarray(malla.vert_properties)[:, :3].astype(np.float64)
    guardar_stl(ruta, v, np.asarray(malla.tri_verts))
    return pieza.volume()


def previa_cubo(caras, ruta, k):
    """Las 4 caras encendidas, una junto a otra."""
    imgs = []
    for esp in caras:
        tmp = Path(ruta).with_suffix(".tmp.png")
        vista_previa(esp, tmp, k=k)
        imgs.append(Image.open(tmp).copy())
        tmp.unlink()
    w, h = imgs[0].size
    sep = max(4, w // 40)
    lienzo = Image.new("RGB", (4 * w + 3 * sep, h), (17, 17, 17))
    for i, im in enumerate(imgs):
        lienzo.paste(im, (i * (w + sep), 0))
    lienzo.thumbnail((1600, 1600))
    lienzo.save(ruta, format="PNG")


def generar(fotos, carpeta, lado=80.0, material="pla", resolucion=0.2, encuadres=None, mejorar=True,
            previa=None):
    """Escribe cara1..4.stl, base.stl y tapa.stl en `carpeta`. Devuelve un resumen."""
    if len(fotos) != 4:
        raise ValueError("el cubo lleva 4 fotos")
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    m = medidas(lado, material)
    encuadres = encuadres or [(0.5, 0.5, 1.0)] * 4
    densidad = 1.27 if material == "petg" else 1.24
    mapas, mm3 = [], 0.0
    for i, (foto, enc) in enumerate(zip(fotos, encuadres), 1):
        esp = espesores_cara(foto, m, material, resolucion, enc, mejorar)
        v, caras = cara(esp, m)
        guardar_stl(carpeta / f"cara{i}.stl", v, caras)
        tri = v[caras]
        mm3 += abs(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()) / 6
        mapas.append(esp)
    mm3_soporte = guardar_manifold(carpeta / "base.stl", base(m)) + guardar_manifold(carpeta / "tapa.stl", tapa(m))
    if previa:
        previa_cubo(mapas, previa, MATERIALES[material]["k"])
    afuera = lado + 2 * m["holgura"] + 2 * m["pared"]
    alto = m["alto_base"] - m["ranura"] + lado + m["tapa"] - m["ranura"]
    return {"medidas": f"{afuera:.0f} x {afuera:.0f} x {alto:.0f} mm",
            "gramos": round(float(mm3) / 1000 * densidad, 1),                # caras en blanco
            "gramos_base_tapa": round(float(mm3_soporte) / 1000 * 1.24, 1)}  # PLA de color


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("fotos", nargs=4)
    p.add_argument("--lado", type=float, default=80)
    p.add_argument("--material", choices=sorted(MATERIALES), default="pla")
    p.add_argument("--resolucion", type=float, default=0.2)
    p.add_argument("--previa")
    p.add_argument("--salida", default="cubo")
    a = p.parse_args()
    r = generar(a.fotos, a.salida, a.lado, a.material, a.resolucion, previa=a.previa)
    print(r)


if __name__ == "__main__":
    main()
