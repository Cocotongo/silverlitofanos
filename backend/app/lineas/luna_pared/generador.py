"""Generador de lunas de pared: cuadro redondo con el relieve de la Luna, iluminado de lado.

Piezas (todas caben en la cama de 220 x 220 de la Ender-3 V3 KE hasta Ø410 mm):
  - 4 losetas (cuartos de circulo) con el relieve, en blanco. Plano abajo, relieve arriba.
  - 4 piezas del marco de atras (aros + rayos), unidas con colas de milano. Las juntas del marco
    quedan a 22.5 grados de las de las losetas, asi cada loseta amarra dos piezas del marco.
    Arriba lleva un ojo de cerradura para colgarla de un clavo.
  - 4 arcos del aro de afuera (en negro): pestana abajo donde asienta el marco, pared donde se pega
    la tira LED mirando al centro (la luz rasante marca los crateres) y un labio a 45 grados arriba
    que tapa la tira. Un arco lleva el agujero del cable.

El relieve sale de `relieve.png` (cara visible de la Luna, proyeccion ortografica del modelo de
alturas LOLA del CGI Moon Kit de la NASA, dominio publico; se regenera con
tools/preparar_luna_pared.py).

Uso:
  python -m app.lineas.luna_pared.generador --diametro 400 --carpeta piezas --previa previa.png
"""
import argparse
from pathlib import Path

import numpy as np
from manifold3d import CrossSection, Manifold
from PIL import Image

from ..litofano.generador import guardar_stl

RELIEVE = Path(__file__).with_name("relieve.png")
CAMA = 220.0
DENSIDAD = {"pla": 1.24, "petg": 1.27}


def medidas(diametro=400.0, alto_relieve=5.0):
    R = diametro / 2.0
    m = {
        "R": R,                 # radio de las losetas y del marco
        "base": 2.0,            # piso de la loseta bajo el relieve
        "alto_relieve": alto_relieve,
        "junta": 0.15,          # medio hueco entre losetas
        "marco": 6.0,           # grueso del marco de atras
        "aro_marco": 12.0,      # ancho del aro de afuera del marco
        "barra": 8.0,           # ancho de rayos y aros interiores
        "holgura": 0.3,         # entre marco/losetas y el aro
        "pared": 3.0,           # pared del aro
        "pestana": 6.0,         # pestana de abajo donde asienta el marco
        "piso": 2.0,
        "tira": 12.0,           # alto libre para la tira LED (COB de 8-10 mm)
        "labio": 8.0,           # labio que tapa la tira
    }
    m["Ri"] = R + m["holgura"]
    m["Ro"] = m["Ri"] + m["pared"]
    m["z_relieve"] = m["piso"] + m["marco"] + m["base"] + alto_relieve   # punta del relieve
    m["alto"] = m["z_relieve"] + m["tira"] + m["labio"] + 2.0
    if max(m["Ro"], R + 7.0) > CAMA - 4:                # la cola de milano del marco sobresale 7 mm
        raise ValueError(f"Ø{diametro:.0f} no cabe en la cama de {CAMA:.0f} mm en 4 piezas (max Ø410)")
    return m


# ---------------------------------------------------------------- relieve y losetas

def _relieve():
    return np.asarray(Image.open(RELIEVE).convert("L"), dtype=np.float64) / 255.0


def alturas(x, y, R, mapa=None):
    """Relieve (0-1) en coordenadas mm con el centro de la luna en el origen (y hacia el norte)."""
    mapa = _relieve() if mapa is None else mapa
    n = mapa.shape[0]
    esc = (R + 1.0) / R                      # el disco del mapa queda 1 mm mas grande que la loseta
    u = (x / (R * esc) + 1) / 2 * n - 0.5
    v = (1 - y / (R * esc)) / 2 * n - 0.5
    u0 = np.clip(np.floor(u).astype(int), 0, n - 2)
    v0 = np.clip(np.floor(v).astype(int), 0, n - 2)
    fu, fv = np.clip(u - u0, 0, 1), np.clip(v - v0, 0, 1)
    return (mapa[v0, u0] * (1 - fu) * (1 - fv) + mapa[v0, u0 + 1] * fu * (1 - fv)
            + mapa[v0 + 1, u0] * (1 - fu) * fv + mapa[v0 + 1, u0 + 1] * fu * fv)


def _bloque_altura(z):
    """Malla cerrada de un campo de alturas z[fila, col] (paso 1) con piso plano en z=0.

    El piso es un abanico desde el centro, asi no duplica los triangulos de arriba.
    """
    f, c = z.shape
    jj, ii = np.meshgrid(np.arange(c), np.arange(f))
    arriba = np.stack([jj, ii, z], -1).reshape(-1, 3).astype(np.float64)
    idx = np.arange(f * c).reshape(f, c)
    a, b, d, e = idx[:-1, :-1], idx[:-1, 1:], idx[1:, :-1], idx[1:, 1:]
    tri = [np.stack([a, b, d], -1).reshape(-1, 3), np.stack([b, e, d], -1).reshape(-1, 3)]
    # contorno en sentido antihorario visto desde arriba
    borde = np.concatenate([idx[0, :], idx[1:, -1], idx[-1, -2::-1], idx[-2:0:-1, 0]])
    nb = len(borde)
    abajo = arriba[borde].copy()
    abajo[:, 2] = 0
    base_ab = len(arriba)
    centro = base_ab + nb
    v = np.vstack([arriba, abajo, [[(c - 1) / 2, (f - 1) / 2, 0]]])
    k = np.arange(nb)
    k2 = (k + 1) % nb
    sup, inf = borde[k], base_ab + k
    sup2, inf2 = borde[k2], base_ab + k2
    tri.append(np.stack([sup, inf, sup2], -1))
    tri.append(np.stack([sup2, inf, inf2], -1))
    tri.append(np.stack([np.full(nb, centro), inf2, inf], -1))
    return v, np.vstack(tri)


def _a_manifold(v, caras):
    from manifold3d import Mesh
    t = v[caras]
    vol = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()
    if vol < 0:
        caras = caras[:, ::-1]
    return Manifold(Mesh(vert_properties=v.astype(np.float32), tri_verts=caras.astype(np.uint32)))


def loseta(m, cuadrante, resolucion=0.6, mapa=None):
    """Loseta del cuadrante 0..3 (0 = noreste, luego antihorario), en coordenadas de impresion
    (esquina del centro de la luna en el origen, el cuarto de circulo hacia +x +y)."""
    R, j = m["R"], m["junta"]
    n = int(np.ceil(R / resolucion)) + 1
    s = np.linspace(0, R, n)
    X, Y = np.meshgrid(s, s)
    # girar el cuadrante 0 (noreste) al que toca
    ang = cuadrante * np.pi / 2
    xm = X * np.cos(ang) - Y * np.sin(ang)
    ym = X * np.sin(ang) + Y * np.cos(ang)
    z = m["base"] + alturas(xm, ym, R, mapa) * m["alto_relieve"]
    v, caras = _bloque_altura(z)
    v[:, :2] *= R / (n - 1)
    bloque = _a_manifold(v, caras)
    disco = Manifold.cylinder(m["alto_relieve"] + m["base"] + 2, R - j, R - j, 720).translate([0, 0, -1])
    corte = Manifold.cube([R, R, m["alto_relieve"] + m["base"] + 4]).translate([j, j, -2])
    return bloque ^ disco ^ corte


# ---------------------------------------------------------------- marco de atras

def _rect(largo, ancho, ang, desde=0.0):
    c = CrossSection.square([largo, ancho]).translate([desde, -ancho / 2])
    return c.rotate(np.degrees(ang))


def _anillo(r_ext, r_int):
    return CrossSection.circle(r_ext, 360) - CrossSection.circle(r_int, 360)


def _cuña(a0, a1, r):
    pts = [(0.0, 0.0)] + [(r * np.cos(a), r * np.sin(a)) for a in np.linspace(a0, a1, 64)]
    return CrossSection([pts])


def _cola(r, ang, holgura=0.0):
    """Cola de milano tangente al aro de radio r, saliendo de la junta en el angulo ang."""
    cuello, cabeza, largo = 6.0 + 2 * holgura, 10.0 + 2 * holgura, 7.0 + holgura
    pts = [(-1.0, -cuello / 2), (0.0, -cuello / 2), (largo, -cabeza / 2),
           (largo, cabeza / 2), (0.0, cuello / 2), (-1.0, cuello / 2)]
    # local: x a lo largo de la tangente (antihorario), y radial; en el angulo 0 la tangente es +Y
    return CrossSection([[(r + y, x) for x, y in pts[::-1]]]).rotate(np.degrees(ang))


def marco_2d(m):
    R, b = m["R"] - m["junta"], m["barra"]
    r_medio, r_centro = R * 0.55, R * 0.16
    forma = (_anillo(R, R - m["aro_marco"]) + _anillo(r_medio + b / 2, r_medio - b / 2)
             + _anillo(r_centro + b / 2, r_centro - b / 2))
    for k in range(8):                                     # rayos bajo las juntas de las losetas
        forma += _rect(R - r_centro - 1, b, k * np.pi / 4, r_centro)
    # cojin para el ojo de cerradura, arriba sobre el aro medio
    forma += CrossSection.square([26, 30]).translate([-13, r_medio - 15])
    return forma, r_medio, r_centro


def pieza_marco(m, k):
    """Pieza k (0..3) del marco, entre 22.5 + 90k y 112.5 + 90k grados, girada para imprimir."""
    forma, r_medio, _ = marco_2d(m)
    R = m["R"] - m["junta"]
    a0 = np.radians(22.5 + 90 * k)
    a1 = a0 + np.pi / 2
    radios = (R - m["aro_marco"] / 2, r_medio)
    p = forma ^ _cuña(a0, a1, R + 5)
    for r in radios:
        p = p + (_cola(r, a1) ^ CrossSection.circle(R, 360))
        p = p - _cola(r, a0, holgura=0.2)
    pieza = Manifold.extrude(p, m["marco"])
    if k == 0:                                            # ojo de cerradura (pieza de arriba)
        y0 = r_medio - 6
        hueco = Manifold.cylinder(m["marco"] + 2, 4.5, 4.5, 48).translate([0, y0, -1])
        ranura = Manifold.cube([4.5, 10, m["marco"] + 2]).translate([-2.25, y0, -1])
        cabeza = Manifold.cube([9.5, 14, 3.5]).translate([-4.75, y0 - 4, m["marco"] - 3.5])
        pieza = pieza - hueco - ranura - cabeza
    return pieza.rotate([0, 0, -np.degrees(a0)])


# ---------------------------------------------------------------- aro con la tira LED

def perfil_aro(m):
    Ri, Ro, H = m["Ri"], m["Ro"], m["alto"]
    L, P, piso = m["labio"], m["pestana"], m["piso"]
    pts = [(Ro, 0), (Ro, H), (Ri - L, H), (Ri - L, H - 2), (Ri, H - 2 - L),
           (Ri, piso), (Ri - P, piso), (Ri - P, 0)]
    return CrossSection([pts])


def pieza_aro(m, k):
    """Arco k (0..3) del aro, entre 45 + 90k y 135 + 90k grados, girado para imprimir."""
    arco = Manifold.revolve(perfil_aro(m), 720, 90.0)      # de 0 a 90 grados
    if k == 2:                                             # el de abajo lleva la salida del cable
        z = m["z_relieve"] + m["tira"] / 2
        cable = (Manifold.cylinder(m["pared"] + 4, 3.0, 3.0, 32)
                 .rotate([0, 90, 0]).translate([m["Ri"] - 2, 0, z]).rotate([0, 0, 45]))
        arco = arco - cable
    return arco


# ---------------------------------------------------------------- salida

def guardar(ruta, pieza):
    malla = pieza.to_mesh()
    v = np.asarray(malla.vert_properties)[:, :3].astype(np.float64)
    guardar_stl(ruta, v, np.asarray(malla.tri_verts))
    return float(pieza.volume())


def vista_previa(m, ruta, lado_px=700, mapa=None):
    """La luna encendida: luz rasante desde todo el borde, como la tira LED del aro."""
    R = m["R"]
    s = (np.arange(lado_px) + 0.5) / lado_px * 2 * R - R
    X, Y = np.meshgrid(s, -s)
    z = alturas(X, Y, R, mapa) * m["alto_relieve"]
    paso = 2 * R / lado_px
    gy, gx = np.gradient(z, paso)
    r = np.hypot(X, Y) + 1e-9
    # la luz llega desde el borde hacia el centro: ilumina las laderas que miran hacia afuera
    luz = np.clip(0.7 - 2.2 * (gx * X + gy * Y) / r, 0, 1.4)
    luz *= 0.8 + 0.25 * (r / R)                             # mas brillante cerca de la tira
    luz = np.clip(luz / 1.25, 0, 1)
    fondo = r > R
    rgb = np.stack([luz * 240, luz * 242, luz * 245], -1)
    aro = (r > R) & (r < R + m["pared"] * 3)
    rgb[fondo] = [32, 32, 36]
    rgb[aro] = [12, 12, 12]
    borde = (r > R - 3) & (r <= R)
    rgb[borde] = [255, 255, 250]
    Image.fromarray(rgb.astype(np.uint8)).save(ruta, format="PNG")


def generar(carpeta, diametro=400.0, alto_relieve=5.0, material="pla", resolucion=0.6, previa=None):
    m = medidas(diametro, alto_relieve)
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    mapa = _relieve()
    mm3_losetas = sum(guardar(carpeta / f"loseta{i + 1}.stl", loseta(m, i, resolucion, mapa)) for i in range(4))
    mm3_marco = sum(guardar(carpeta / f"marco{k + 1}.stl", pieza_marco(m, k)) for k in range(4))
    mm3_aro = sum(guardar(carpeta / f"aro{k + 1}.stl", pieza_aro(m, k)) for k in range(4))
    if previa:
        vista_previa(m, previa, mapa=mapa)
    d = DENSIDAD.get(material, 1.24)
    return {
        "medidas": f"Ø{2 * m['Ro']:.0f} x {m['alto']:.0f} mm",
        "gramos": round(mm3_losetas / 1000 * d, 1),                 # losetas en blanco
        "gramos_marco": round(mm3_marco / 1000 * 1.24, 1),          # marco (cualquier color)
        "gramos_aro": round(mm3_aro / 1000 * 1.24, 1),              # aro en negro
        "tira_cm": round(2 * np.pi * m["Ri"] / 10 + 5),             # tira LED a lo largo del aro
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--diametro", type=float, default=400)
    p.add_argument("--alto-relieve", type=float, default=5)
    p.add_argument("--material", default="pla")
    p.add_argument("--resolucion", type=float, default=0.6)
    p.add_argument("--carpeta", default="piezas")
    p.add_argument("--previa")
    a = p.parse_args()
    print(generar(a.carpeta, a.diametro, a.alto_relieve, a.material, a.resolucion, a.previa))


if __name__ == "__main__":
    main()
