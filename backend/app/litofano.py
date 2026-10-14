"""Generador de litofanos: foto -> STL (panel plano o cilindro).

Uso:
  python litofano.py foto.jpg --forma panel   --ancho 100 --salida panel.stl
  python litofano.py foto.jpg --forma cilindro --diametro 80 --alto 100 --salida lampara.stl

Zonas oscuras de la foto = material grueso (deja pasar poca luz).
Zonas claras = material delgado (deja pasar mucha luz).
"""
import argparse
import numpy as np
from PIL import Image, ImageOps


# Espesores (mm) y absorcion de luz aproximada por material, para filamento BLANCO.
# El PETG es mas translucido que el PLA, asi que necesita mas grosor para el mismo contraste.
MATERIALES = {
    "pla":  {"min": 0.8, "max": 3.0, "k": 1.2},
    "petg": {"min": 1.0, "max": 3.6, "k": 0.9},
}


def cargar_espesores(ruta, ancho_px, alto_px, t_min, t_max, invertir=False):
    img = Image.open(ruta)
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageOps.autocontrast(img, cutoff=1)
    # recorta al centro con la proporcion del destino para no deformar la foto
    img = ImageOps.fit(img, (ancho_px, alto_px), Image.LANCZOS)
    brillo = np.asarray(img, dtype=np.float64) / 255.0
    if invertir:
        brillo = 1.0 - brillo
    # fila 0 = parte de arriba de la foto -> la ponemos arriba en Z
    brillo = brillo[::-1, :]
    return t_max - brillo * (t_max - t_min)


def _quads(idx_a, idx_b, idx_c, idx_d):
    """Dos triangulos por cuadrilatero a-b-c-d (antihorario)."""
    return np.concatenate([
        np.stack([idx_a, idx_b, idx_c], -1).reshape(-1, 3),
        np.stack([idx_a, idx_c, idx_d], -1).reshape(-1, 3),
    ])


def malla_cerrada(exterior, interior, cerrar_columnas):
    """Une dos rejillas (filas x columnas x 3) en un solido cerrado.

    exterior: cara iluminada/relieve. interior: cara trasera.
    cerrar_columnas: True para cilindro (la ultima columna se une con la primera).
    """
    f, c, _ = exterior.shape
    v = np.concatenate([exterior.reshape(-1, 3), interior.reshape(-1, 3)])
    off = f * c
    ids = np.arange(f * c).reshape(f, c)
    if cerrar_columnas:
        ids = np.concatenate([ids, ids[:, :1]], axis=1)

    a, b, cc, d = ids[:-1, :-1], ids[:-1, 1:], ids[1:, 1:], ids[1:, :-1]
    caras = [
        _quads(a, b, cc, d),                         # exterior
        _quads(a + off, d + off, cc + off, b + off),  # interior (normal opuesta)
    ]
    # paredes: borde inferior (fila 0) y superior (ultima fila)
    r0, r1 = ids[0], ids[-1]
    caras.append(_quads(r0[1:], r0[:-1], r0[:-1] + off, r0[1:] + off))
    caras.append(_quads(r1[:-1], r1[1:], r1[1:] + off, r1[:-1] + off))
    if not cerrar_columnas:
        c0, c1 = ids[:, 0], ids[:, -1]
        caras.append(_quads(c0[:-1], c0[1:], c0[1:] + off, c0[:-1] + off))
        caras.append(_quads(c1[1:], c1[:-1], c1[:-1] + off, c1[1:] + off))
    return v, np.concatenate(caras)


def panel(esp, ancho_mm, borde_mm=0.0):
    f, c = esp.shape
    alto_mm = ancho_mm * f / c
    x = np.linspace(0, ancho_mm, c)
    z = np.linspace(0, alto_mm, f)
    X, Z = np.meshgrid(x, z)
    ext = np.stack([X, -esp, Z], -1)          # relieve hacia -Y (cara que ve la gente)
    inte = np.stack([X, np.zeros_like(X), Z], -1)
    return malla_cerrada(ext, inte, cerrar_columnas=False)


def cilindro(esp, diametro_mm, alto_mm):
    f, c = esp.shape
    r_in = diametro_mm / 2.0
    ang = np.linspace(0, 2 * np.pi, c, endpoint=False)
    z = np.linspace(0, alto_mm, f)
    A, Z = np.meshgrid(ang, z)
    # angulo creciente = hacia la derecha vista desde fuera (sin espejo)
    cx, sy = np.cos(A), np.sin(A)
    R = r_in + esp
    ext = np.stack([R * cx, R * sy, Z], -1)
    inte = np.stack([r_in * cx, r_in * sy, Z], -1)
    return malla_cerrada(ext, inte, cerrar_columnas=True)


def con_marco(esp, marco_mm, resolucion, grosor):
    """Agrega un marco solido alrededor del panel para que sea mas rigido."""
    n = int(round(marco_mm / resolucion))
    return np.pad(esp, n, constant_values=grosor) if n > 0 else esp


def vista_previa(esp, ruta, k=1.2):
    """Simula el litofano encendido: la luz pasa ~exp(-k * espesor)."""
    luz = np.exp(-k * esp)
    luz = (luz - luz.min()) / (luz.max() - luz.min())
    calido = np.array([255, 214, 160]) / 255.0
    rgb = (luz[::-1, :, None] * calido * 255).astype(np.uint8)
    Image.fromarray(rgb).save(ruta)


def guardar_stl(ruta, v, caras):
    tri = v[caras]
    volumen = np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()
    if volumen < 0:  # normales hacia dentro: invertir orientacion
        tri = tri[:, ::-1]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    largo = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.divide(n, largo, out=np.zeros_like(n), where=largo > 0)
    datos = np.zeros(len(caras), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    datos["n"], datos["v"] = n, tri
    with open(ruta, "wb") as fh:
        fh.write(b"SilVerLitofanos".ljust(80, b" "))
        fh.write(np.uint32(len(caras)).tobytes())
        fh.write(datos.tobytes())


def generar(foto, salida_stl, forma="panel", material="pla", ancho=100.0, diametro=80.0,
            alto=100.0, resolucion=0.2, marco=3.0, invertir=False, previa=None):
    """Genera el STL (y opcionalmente la vista previa). Devuelve un resumen."""
    mat = MATERIALES[material]
    if forma == "panel":
        w, h = ImageOps.exif_transpose(Image.open(foto)).size
        cols = int(ancho / resolucion)
        filas = int(cols * h / w)
        esp = cargar_espesores(foto, cols, filas, mat["min"], mat["max"], invertir)
        esp = con_marco(esp, marco, resolucion, mat["max"] + 1.0)
        v, caras = panel(esp, ancho + 2 * marco)
        medidas = f"{ancho + 2 * marco:.0f} x {(ancho + 2 * marco) * esp.shape[0] / esp.shape[1]:.0f} mm"
    elif forma == "cilindro":
        cols = int(np.pi * diametro / resolucion)
        filas = int(alto / resolucion)
        esp = cargar_espesores(foto, cols, filas, mat["min"], mat["max"], invertir)
        v, caras = cilindro(esp, diametro, alto)
        medidas = f"Ø{diametro:.0f} x {alto:.0f} mm"
    else:
        raise ValueError(f"forma desconocida: {forma}")
    guardar_stl(salida_stl, v, caras)
    if previa:
        vista_previa(esp, previa, k=mat["k"])
    tri = v[caras]
    volumen_mm3 = abs(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()) / 6
    densidad = 1.27 if material == "petg" else 1.24
    return {"triangulos": int(len(caras)), "medidas": medidas,
            "gramos": round(volumen_mm3 / 1000 * densidad, 1)}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("foto")
    p.add_argument("--forma", choices=["panel", "cilindro"], default="panel")
    p.add_argument("--ancho", type=float, default=100, help="panel: ancho en mm")
    p.add_argument("--diametro", type=float, default=80, help="cilindro: diametro interior en mm")
    p.add_argument("--alto", type=float, default=100, help="cilindro: alto en mm")
    p.add_argument("--material", choices=sorted(MATERIALES), default="pla")
    p.add_argument("--min", type=float, help="espesor minimo mm (zonas claras); por defecto segun material")
    p.add_argument("--max", type=float, help="espesor maximo mm (zonas oscuras); por defecto segun material")
    p.add_argument("--resolucion", type=float, default=0.2, help="mm por pixel")
    p.add_argument("--invertir", action="store_true")
    p.add_argument("--marco", type=float, default=3.0, help="panel: ancho del marco en mm (0 = sin marco)")
    p.add_argument("--previa", help="guardar imagen PNG simulando el litofano encendido")
    p.add_argument("--salida", default="litofano.stl")
    a = p.parse_args()
    mat = MATERIALES[a.material]
    a.min = mat["min"] if a.min is None else a.min
    a.max = mat["max"] if a.max is None else a.max

    if a.forma == "panel":
        img = Image.open(a.foto)
        w, h = ImageOps.exif_transpose(img).size
        cols = int(a.ancho / a.resolucion)
        filas = int(cols * h / w)
        esp = cargar_espesores(a.foto, cols, filas, a.min, a.max, a.invertir)
        esp = con_marco(esp, a.marco, a.resolucion, a.max + 1.0)
        v, caras = panel(esp, a.ancho + 2 * a.marco)
    else:
        cols = int(np.pi * a.diametro / a.resolucion)
        filas = int(a.alto / a.resolucion)
        esp = cargar_espesores(a.foto, cols, filas, a.min, a.max, a.invertir)
        v, caras = cilindro(esp, a.diametro, a.alto)

    guardar_stl(a.salida, v, caras)
    if a.previa:
        vista_previa(esp, a.previa, k=mat["k"])
    print(f"{a.salida}: {len(caras):,} triangulos, {esp.shape[1]}x{esp.shape[0]} px, "
          f"espesor {esp.min():.2f}-{esp.max():.2f} mm")


if __name__ == "__main__":
    main()
