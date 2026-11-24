"""Generador de lunas de pared: cuadro redondo con el relieve de la Luna, iluminado de lado.

Todas las piezas caben en la cama de 220 x 220 de la Ender-3 V3 KE:
  - Losetas blancas con el relieve (plano abajo, relieve arriba). Hasta Ø410 son 4 cuartos de
    circulo; mas grande, 4 cuartos al centro y un anillo de 8 o 12 sectores alrededor.
  - Marco de atras (aros + rayos bajo todas las juntas de las losetas), en piezas unidas con colas
    de milano. Las juntas del marco quedan corridas respecto a las de las losetas, asi cada loseta
    amarra dos piezas del marco. Arriba lleva un ojo de cerradura para colgarla de un clavo.
  - Aro de afuera en arcos (en negro): pestana abajo donde asienta el marco, pared donde se pega
    la tira LED mirando al centro (la luz rasante marca los crateres) y un labio a 45 grados arriba
    que tapa la tira. El arco de abajo lleva el agujero del cable.

El relieve sale de `relieve.png` (cara visible de la Luna, proyeccion ortografica del modelo de
alturas LOLA del CGI Moon Kit de la NASA, dominio publico; se regenera con
tools/preparar_luna_pared.py).

Uso:
  python -m app.lineas.luna_pared.generador --diametro 600 --carpeta piezas --previa previa.png
"""
import argparse
from pathlib import Path

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold, Mesh
from PIL import Image

from ..litofano.generador import guardar_stl

RELIEVE = Path(__file__).with_name("relieve.png")
CAMA = 220.0
UTIL = CAMA - 4.0          # lo que usamos de la cama, con margen
COLA = 7.0                 # lo que sobresale una cola de milano
DENSIDAD = {"pla": 1.24, "petg": 1.27}


def medidas(diametro=400.0, alto_relieve=5.0):
    R = diametro / 2.0
    m = {
        "R": R,                 # radio de las losetas y del marco
        "base": 2.0,            # piso de la loseta bajo el relieve
        "alto_relieve": alto_relieve,
        "junta": 0.15,          # medio hueco entre losetas
        "marco": 6.0,           # grueso del marco de atras
        "aro_marco": 12.0,      # ancho de los aros grandes del marco
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
    m.update(_disposicion(m))
    return m


def _disposicion(m):
    """Como se parte la luna para que cada pieza quepa en la cama.

    r1: radio de la zona del centro (4 cuartos). n: sectores del anillo de afuera (0 = no hay).
    Las juntas de las losetas de afuera quedan en multiplos de 360/n (incluye 0, 90, 180, 270) y las
    del marco del centro en 22.5 + 90k, que caen lejos de ellas con n = 8 o 12.
    """
    R, Ro, a = m["R"], m["Ro"], m["aro_marco"]
    if max(Ro, R + COLA) <= UTIL:
        return {"r1": R, "n": 0, "n_aro": 4}
    r1 = min(round(0.6 * R), UTIL - COLA - a / 2 - 1)
    for n in (8, 12):
        ancho = 2 * Ro * np.sin(np.pi / n) + 2 * COLA
        fondo = Ro - r1 * np.cos(np.pi / n)
        if ancho <= UTIL and fondo <= UTIL:
            return {"r1": float(r1), "n": n, "n_aro": n}
    raise ValueError(f"Ø{2 * R:.0f} no cabe en la cama de {CAMA:.0f} mm (max Ø770)")


def piezas_por_tipo(m):
    return {"losetas": 4 + m["n"], "marco": 4 + m["n"], "aro": m["n_aro"]}


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
    t = v[caras]
    vol = np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum()
    if vol < 0:
        caras = caras[:, ::-1]
    return Manifold(Mesh(vert_properties=v.astype(np.float32), tri_verts=caras.astype(np.uint32)))


def _cuña(a0, a1, r):
    pts = [(0.0, 0.0)] + [(r * np.cos(a), r * np.sin(a)) for a in np.linspace(a0, a1, 96)]
    return CrossSection([pts])


def _anillo(r_ext, r_int):
    c = CrossSection.circle(r_ext, 720)
    return c - CrossSection.circle(r_int, 720) if r_int > 0 else c


def regiones_losetas(m):
    """[(region 2D en coordenadas de la luna, angulo medio, angulo que abarca)] de cada loseta."""
    R, r1, n, j = m["R"], m["r1"], m["n"], m["junta"]
    out = []
    for k in range(4):                                     # cuartos del centro: NE, NO, SO, SE
        a0 = k * np.pi / 2
        out.append((_anillo(r1, 0) ^ _cuña(a0, a0 + np.pi / 2, r1 + 10), a0 + np.pi / 4, np.pi / 2))
    for i in range(n):                                     # sectores de afuera
        a0 = 2 * np.pi * i / n
        out.append((_anillo(R, r1) ^ _cuña(a0, a0 + 2 * np.pi / n, R + 10), a0 + np.pi / n, 2 * np.pi / n))
    return [(reg.offset(-j, JoinType.Miter), mid, ab) for reg, mid, ab in out]


def loseta(m, region, resolucion=0.6, mapa=None):
    """Campo de alturas del relieve recortado a la region (coordenadas de la luna)."""
    x0, y0, x1, y1 = region.bounds()
    nx = int(np.ceil((x1 - x0) / resolucion)) + 1
    ny = int(np.ceil((y1 - y0) / resolucion)) + 1
    X, Y = np.meshgrid(np.linspace(x0, x1, nx), np.linspace(y0, y1, ny))
    z = m["base"] + alturas(X, Y, m["R"], mapa) * m["alto_relieve"]
    v, caras = _bloque_altura(z)
    v[:, 0] = x0 + v[:, 0] * (x1 - x0) / (nx - 1)
    v[:, 1] = y0 + v[:, 1] * (y1 - y0) / (ny - 1)
    alto = m["base"] + m["alto_relieve"] + 2
    return _a_manifold(v, caras) ^ Manifold.extrude(region, alto + 2).translate([0, 0, -1])


# ---------------------------------------------------------------- marco de atras

def _rayo(r0, r1, ancho, ang):
    c = CrossSection.square([r1 - r0, ancho]).translate([r0, -ancho / 2])
    return c.rotate(np.degrees(ang))


def _cola(p0, d, holgura=0.0):
    """Cola de milano que sale del punto p0 en la direccion d (vector unitario)."""
    cuello, cabeza, largo = 6.0 + 2 * holgura, 10.0 + 2 * holgura, COLA + holgura
    d = np.asarray(d, float)
    n = np.array([-d[1], d[0]])
    loc = [(-1.0, -cuello / 2), (0.0, -cuello / 2), (largo, -cabeza / 2),
           (largo, cabeza / 2), (0.0, cuello / 2), (-1.0, cuello / 2)]
    pts = [tuple(np.asarray(p0) + x * d + y * n) for x, y in loc]
    return CrossSection([pts])


def _cola_tangente(r, ang, holgura=0.0):
    return _cola((r * np.cos(ang), r * np.sin(ang)), (-np.sin(ang), np.cos(ang)), holgura)


def _cola_radial(r, ang, holgura=0.0):
    """Sale del radio r hacia el centro (del anillo de afuera al aro del centro)."""
    return _cola((r * np.cos(ang), r * np.sin(ang)), (-np.cos(ang), -np.sin(ang)), holgura)


def marco_2d(m):
    """Forma completa del marco y los radios donde van las colas de milano."""
    R, r1, n = m["R"] - m["junta"], m["r1"], m["n"]
    a, b = m["aro_marco"], m["barra"]
    if n == 0:
        r_c, borde = R - a / 2, R                          # aro grande del centro = aro de afuera
    else:
        r_c, borde = r1, r1 + a / 2
    r_medio, r_hub = 0.55 * r_c, 0.16 * r_c
    centro = (_anillo(r_c + a / 2, r_c - a / 2) + _anillo(r_medio + b / 2, r_medio - b / 2)
              + _anillo(r_hub + b / 2, r_hub - b / 2))
    for k in range(8):
        centro += _rayo(r_hub, r_c, b, k * np.pi / 4)
    centro += CrossSection.square([26, 30]).translate([-13, r_medio - 15])   # cojin del ojo de cerradura
    afuera, r_afuera = None, ()
    if n:
        r_mid2 = (borde + R) / 2
        afuera = _anillo(R, R - a) + _anillo(r_mid2 + b / 2, r_mid2 - b / 2)
        for i in range(n):
            afuera += _rayo(borde - 0.01, R - a / 2, b, 2 * np.pi * i / n)
        afuera = afuera - CrossSection.circle(borde, 720)
        r_afuera = (R - a / 2, r_mid2)
    return {"centro": centro, "afuera": afuera, "borde": borde, "r_centro": (r_c, r_medio),
            "r_afuera": r_afuera, "r_medio": r_medio}


def piezas_marco(m):
    """[(pieza 3D en coordenadas de la luna, angulo medio, angulo que abarca)]."""
    f = marco_2d(m)
    R, n, borde = m["R"] - m["junta"], m["n"], f["borde"]
    out = []
    radiales = [2 * np.pi * i / n for i in range(n)]
    for k in range(4):
        a0 = np.radians(22.5 + 90 * k)
        a1 = a0 + np.pi / 2
        p = f["centro"] ^ _cuña(a0, a1, borde + 20)
        for r in f["r_centro"]:
            p = p + (_cola_tangente(r, a1) ^ CrossSection.circle(borde, 720))
            p = p - _cola_tangente(r, a0, 0.2)
        for ang in radiales:                                # huecos de las colas del anillo de afuera
            p = p - _cola_radial(borde, ang, 0.2)
        pieza = Manifold.extrude(p, m["marco"])
        if k == 0:                                         # ojo de cerradura, arriba
            y0 = f["r_medio"] - 6
            hueco = Manifold.cylinder(m["marco"] + 2, 4.5, 4.5, 48).translate([0, y0, -1])
            ranura = Manifold.cube([4.5, 10, m["marco"] + 2]).translate([-2.25, y0, -1])
            cabeza = Manifold.cube([9.5, 14, 3.5]).translate([-4.75, y0 - 4, m["marco"] - 3.5])
            pieza = pieza - hueco - ranura - cabeza
        out.append((pieza, a0 + np.pi / 4, np.pi / 2))
    for i in range(n):                                     # juntas a medio camino entre las de las losetas
        a0 = 2 * np.pi * i / n + np.pi / n
        a1 = a0 + 2 * np.pi / n
        p = f["afuera"] ^ _cuña(a0, a1, R + 20)
        for r in f["r_afuera"]:
            p = p + (_cola_tangente(r, a1) ^ CrossSection.circle(R, 720))
            p = p - _cola_tangente(r, a0, 0.2)
        p = p + _cola_radial(borde, a0 + np.pi / n)        # al pie del rayo, entra en el aro del centro
        out.append((Manifold.extrude(p, m["marco"]), a0 + np.pi / n, 2 * np.pi / n))
    return out


# ---------------------------------------------------------------- aro con la tira LED

def perfil_aro(m):
    Ri, Ro, H = m["Ri"], m["Ro"], m["alto"]
    L, P, piso = m["labio"], m["pestana"], m["piso"]
    pts = [(Ro, 0), (Ro, H), (Ri - L, H), (Ri - L, H - 2), (Ri, H - 2 - L),
           (Ri, piso), (Ri - P, piso), (Ri - P, 0)]
    return CrossSection([pts])


def piezas_aro(m):
    """[(arco 3D en coordenadas de la luna, angulo medio, angulo que abarca)].

    Las juntas del aro caen entre las de las losetas y las del marco. El arco que pasa por abajo
    (270 grados) lleva la salida del cable.
    """
    na = m["n_aro"]
    paso = 360.0 / na
    inicio = 45.0 if m["n"] == 0 else paso / 4
    z = m["z_relieve"] + m["tira"] / 2
    cable = (Manifold.cylinder(m["pared"] + 4, 3.0, 3.0, 32)
             .rotate([0, 90, 0]).translate([m["Ri"] - 2, 0, z]).rotate([0, 0, 270]))
    out = []
    for k in range(na):
        a0 = inicio + paso * k
        arco = Manifold.revolve(perfil_aro(m), 720, paso).rotate([0, 0, a0])
        if (270 - a0) % 360 < paso:
            arco = arco - cable
        out.append((arco, np.radians(a0 + paso / 2), np.radians(paso)))
    return out


def para_imprimir(pieza, medio, abarca):
    """Gira la pieza para que use bien la cama y la pone en la esquina (0, 0, 0)."""
    destino = 45.0 if abarca >= np.pi / 2 - 1e-9 else 90.0
    p = pieza.rotate([0, 0, destino - np.degrees(medio)])
    x0, y0, z0, *_ = p.bounding_box()
    return p.translate([-x0, -y0, -z0])


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


def armada(m, resolucion=0.6, mapa=None):
    """Todas las piezas en su lugar: {"loseta": [...], "marco": [...], "aro": [...]}.

    Cada elemento es (pieza 3D en coordenadas de la luna, angulo medio, angulo que abarca).
    """
    mapa = _relieve() if mapa is None else mapa
    z0 = m["piso"] + m["marco"]
    losetas = [(loseta(m, reg, resolucion, mapa).translate([0, 0, z0]), mid, ab)
               for reg, mid, ab in regiones_losetas(m)]
    marco = [(p.translate([0, 0, m["piso"]]), mid, ab) for p, mid, ab in piezas_marco(m)]
    return {"loseta": losetas, "marco": marco, "aro": piezas_aro(m)}


def generar(carpeta, diametro=400.0, alto_relieve=5.0, material="pla", resolucion=0.6, previa=None):
    m = medidas(diametro, alto_relieve)
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    mapa = _relieve()
    mm3 = {}
    for tipo, piezas in armada(m, resolucion, mapa).items():
        mm3[tipo] = sum(guardar(carpeta / f"{tipo}{i + 1:02d}.stl", para_imprimir(*p))
                        for i, p in enumerate(piezas))
    if previa:
        vista_previa(m, previa, mapa=mapa)
    d = DENSIDAD.get(material, 1.24)
    cuantas = piezas_por_tipo(m)
    return {
        "medidas": f"Ø{2 * m['Ro']:.0f} x {m['alto']:.0f} mm",
        "gramos": round(mm3["loseta"] / 1000 * d, 1),               # losetas en blanco
        "gramos_marco": round(mm3["marco"] / 1000 * 1.24, 1),       # marco (cualquier color)
        "gramos_aro": round(mm3["aro"] / 1000 * 1.24, 1),           # aro en negro
        "tira_cm": round(2 * np.pi * m["Ri"] / 10 + 5),             # tira LED a lo largo del aro
        "losetas": cuantas["losetas"], "piezas_marco": cuantas["marco"], "piezas_aro": cuantas["aro"],
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
