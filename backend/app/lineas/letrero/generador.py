"""Generador de letreros LED tipo neón: texto -> piezas imprimibles (carcasa + cubierta).

Cada letra es un canal (el trazo de la letra) donde va la tira LED, rodeado por una pared.
Encima del canal va una cubierta difusora que asienta en un escalón. El letrero se corta en
piezas que caben en la cama; si el canal cruza el corte, el LED pasa por ahí mismo; si dos
letras solo se tocan por la pared, se abre un túnel en el piso para pasar la tira.

Todas las medidas salen del perfil (ver Perfil): se pueden cambiar si cambia el proveedor de la tira.
"""
import io
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from manifold3d import CrossSection, FillRule, Manifold, OpType
from PIL import Image, ImageDraw
from shapely import affinity
from shapely.ops import polylabel
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.geometry.polygon import orient
from shapely.ops import nearest_points, unary_union

FUENTES = Path(__file__).parent / "fuentes"
DENSIDAD_PETG = 1.27  # g/cm3


@dataclass
class Perfil:
    """Medidas de construccion (mm). Las de la tira dependen del proveedor."""
    ancho_tira: float = 10.0       # ancho de la tira LED
    holgura_tira: float = 1.0      # espacio libre a cada lado de la tira en canal y tuneles
    alto_tunel: float = 13.0       # alto del tunel de paso entre letras, desde el piso
    profundidad: float = 50.0      # grosor total del letrero
    base: float = 1.0              # piso (va contra la pared)
    fondo_canal: float = 30.0      # altura donde termina el canal y asienta la cubierta
    pared: float = 9.2             # grosor del contorno alrededor del canal
    escalon: float = 1.2           # ensanche por lado del alojamiento de la cubierta
    tapa_pared: float = 0.9
    tapa_frente: float = 0.4
    tapa_holgura: float = 0.3      # juego entre cubierta y carcasa
    holgura_union: float = 0.2     # juego total entre dos piezas que se juntan
    pieza_max: float = 210.0       # medida maxima de una pieza (cama de 220 mm)
    colgador_diam: float = 9.0
    colgador_largo: float = 15.0
    cable_ancho: float = 10.0
    cable_largo: float = 8.0

    @property
    def ancho_minimo(self) -> float:
        return self.ancho_tira + 2 * self.holgura_tira


def fuentes() -> list[str]:
    return sorted(p.stem for p in FUENTES.glob("*.ttf"))


# ---------------------------------------------------------------- texto -> poligonos

class _Aplanar(BasePen):
    """Convierte los contornos de una letra en listas de puntos (curvas muestreadas)."""

    def __init__(self, glyphset, pasos=12):
        super().__init__(glyphset)
        self.anillos, self.actual, self.pasos = [], [], pasos

    def _moveTo(self, p):
        self.actual = [p]

    def _lineTo(self, p):
        self.actual.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = np.array(self.actual[-1])
        t = np.linspace(0, 1, self.pasos + 1)[1:, None]
        pts = ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * np.array(p3)
        self.actual.extend(map(tuple, pts))

    def _qCurveToOne(self, p1, p2):
        p0 = np.array(self.actual[-1])
        t = np.linspace(0, 1, self.pasos + 1)[1:, None]
        pts = ((1 - t) ** 2) * p0 + 2 * (1 - t) * t * np.array(p1) + t ** 2 * np.array(p2)
        self.actual.extend(map(tuple, pts))

    def _closePath(self):
        if len(self.actual) > 2:
            self.anillos.append(self.actual)
        self.actual = []

    _endPath = _closePath


def letras(texto: str, fuente: str, altura: float) -> list[list[Polygon]]:
    """Devuelve, por palabra, la forma de cada letra en mm (altura = alto de las mayusculas)."""
    ruta = FUENTES / f"{fuente}.ttf"
    if not ruta.exists():
        raise ValueError(f"Fuente desconocida: {fuente}")
    f = TTFont(str(ruta))
    cmap, gs, hmtx = f.getBestCmap(), f.getGlyphSet(), f["hmtx"]
    os2 = f["OS/2"] if "OS/2" in f else None
    cap = getattr(os2, "sCapHeight", 0) or 0.7 * f["head"].unitsPerEm
    esc = altura / cap
    palabras, x = [], 0.0
    for palabra in texto.split():
        actual = []
        for ch in palabra:
            nombre = cmap.get(ord(ch))
            if nombre is None:
                raise ValueError(f"La fuente {fuente} no tiene la letra «{ch}»")
            pen = _Aplanar(gs)
            gs[nombre].draw(pen)
            forma = Polygon()
            for anillo in pen.anillos:  # par-impar: los contornos internos son huecos
                forma = forma.symmetric_difference(Polygon(anillo).buffer(0))
            if not forma.is_empty:
                actual.append(affinity.scale(affinity.translate(forma, x), esc, esc, origin=(0, 0)))
            x += hmtx[nombre][0]
        palabras.append(actual)
        x += hmtx[cmap[ord(" ")]][0] if ord(" ") in cmap else 0.3 * f["head"].unitsPerEm
    return palabras


# ---------------------------------------------------------------- 2D -> 3D

def _poligonos(g):
    if g.is_empty:
        return []
    return [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if isinstance(p, Polygon) and p.area > 0.01]


def _seccion(g) -> CrossSection:
    anillos = []
    for p in _poligonos(g):
        p = orient(p, 1.0)
        anillos.append(np.asarray(p.exterior.coords)[:-1])
        anillos.extend(np.asarray(r.coords)[:-1] for r in p.interiors)
    return CrossSection(anillos, FillRule.EvenOdd) if anillos else CrossSection()


def _prisma(g, z0, z1) -> Manifold:
    s = _seccion(g)
    if s.is_empty() or z1 <= z0:
        return Manifold()
    return s.extrude(z1 - z0).translate((0, 0, z0))


def stl_bytes(m: Manifold) -> bytes:
    malla = m.to_mesh()
    v = np.asarray(malla.vert_properties)[:, :3].astype(np.float32)
    tri = v[np.asarray(malla.tri_verts)]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    datos = np.zeros(len(tri), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    datos["n"], datos["v"] = n, tri
    return b"SilVer letrero".ljust(80, b" ") + np.uint32(len(tri)).tobytes() + datos.tobytes()


# ---------------------------------------------------------------- diseno

def _tuneles(canales: list[Polygon], ancho: float):
    """Une cada letra con la siguiente cuando sus canales no se tocan."""
    barras = []
    for a, b in zip(canales, canales[1:]):
        if a.buffer(0.05).intersects(b):
            continue
        pa, pb = nearest_points(a, b)
        # entra un poco en cada canal para que el paso quede abierto
        d = np.array([pb.x - pa.x, pb.y - pa.y])
        d = d / (np.linalg.norm(d) or 1)
        ini = (pa.x - d[0] * ancho / 2, pa.y - d[1] * ancho / 2)
        fin = (pb.x + d[0] * ancho / 2, pb.y + d[1] * ancho / 2)
        barras.append(LineString([ini, fin]).buffer(ancho / 2, cap_style="flat"))
    return unary_union(barras) if barras else Polygon()


def _cortes(contorno, x0, x1, maximo, evitar):
    """Elige donde cortar en vertical para que ninguna pieza pase de `maximo` de ancho.

    Busca, dentro de la ventana permitida, la linea que cruza menos material y no pasa por un tunel.
    """
    cortes, inicio = [], x0
    alto = contorno.bounds[3] - contorno.bounds[1] + 10
    y0 = contorno.bounds[1] - 5
    while x1 - inicio > maximo:
        mejor = None
        for x in np.arange(inicio + maximo * 0.45, inicio + maximo - 1, 1.0):
            linea = box(x - 0.05, y0, x + 0.05, y0 + alto)
            if linea.intersects(evitar):
                continue
            costo = linea.intersection(contorno).area
            if mejor is None or costo < mejor[0]:
                mejor = (costo, x)
        if mejor is None:
            raise ValueError("No encontré dónde cortar las piezas; prueba con letras más chicas o pieza_max mayor")
        cortes.append(mejor[1])
        inicio = mejor[1]
    return cortes


def _colgador(pieza, p: Perfil):
    """Ojo de cerradura en el piso, en la zona mas holgada de la mitad de arriba de la pieza."""
    b = pieza.bounds
    arriba = pieza.intersection(box(b[0], (b[1] + b[3]) / 2, b[2], b[3]))
    zona = max(_poligonos(arriba) or _poligonos(pieza), key=lambda q: q.area)
    c = polylabel(zona, tolerance=0.5)
    r = p.colgador_diam / 2
    ranura = LineString([(c.x, c.y), (c.x, c.y + p.colgador_largo - p.colgador_diam)]).buffer(r / 2, cap_style="round")
    forma = Point(c.x, c.y).buffer(r).union(ranura)
    return forma if pieza.buffer(-1).contains(forma) else Polygon()


def disenar(texto: str, fuente: str, altura: float, p: Perfil) -> dict:
    """Calcula el diseno en 2D: canales, contornos, tuneles y cortes. Sin 3D (rapido)."""
    if p.fondo_canal <= p.base + 1 or p.fondo_canal >= p.profundidad:
        raise ValueError("fondo_canal debe quedar entre la base y la profundidad")
    advertencias, palabras = [], []
    ancho_tunel = p.ancho_minimo
    for formas in letras(texto, fuente, altura):
        if not formas:
            continue
        canal = unary_union(formas)
        # trazos mas delgados que la tira con su holgura
        delgado = canal.difference(canal.buffer(-p.ancho_minimo / 2).buffer(p.ancho_minimo / 2 + 0.01))
        if delgado.area > 0.05 * canal.area:
            advertencias.append(f"Hay trazos más delgados que {p.ancho_minimo:g} mm (tira + holgura): "
                                f"sube la altura de letra o usa otra fuente")
        grupos = sorted(_poligonos(canal), key=lambda q: q.bounds[0])
        tuneles = _tuneles(grupos, ancho_tunel)
        contorno = unary_union([canal.buffer(p.pared), tuneles.buffer(p.pared)])
        palabras.append({"canal": canal, "tuneles": tuneles, "contorno": contorno})
    if not palabras:
        raise ValueError("El texto está vacío")
    # las palabras que se tocan por la pared se juntan; si no, quedan separadas (el cable brinca)
    piezas = []
    for w in palabras:
        b = w["contorno"].bounds
        if b[3] - b[1] > p.pieza_max:
            raise ValueError(f"El letrero mide {b[3] - b[1]:.0f} mm de alto y la pieza máxima es {p.pieza_max:g} mm")
        cortes = _cortes(w["contorno"], b[0], b[2], p.pieza_max, w["tuneles"].buffer(1))
        lims = [b[0] - 1] + cortes + [b[2] + 1]
        trozos = []
        for i, (xa, xb) in enumerate(zip(lims, lims[1:])):
            ga = p.holgura_union / 2 if i > 0 else 0
            gb = p.holgura_union / 2 if i < len(lims) - 2 else 0
            caja = box(xa + ga, b[1] - 1, xb - gb, b[3] + 1)
            trozos.append({"caja": caja, "contorno": w["contorno"].intersection(caja)})
        trozos[-1]["cable"] = True
        for t in trozos:
            t.update(palabra=w)
        piezas.extend(trozos)
    return {"palabras": palabras, "piezas": piezas, "advertencias": list(dict.fromkeys(advertencias))}


def _cable(canal, pieza, p: Perfil):
    """Hueco en el piso para sacar el cable: al final del canal (lo mas a la derecha)."""
    c = canal.intersection(pieza)
    if c.is_empty:
        return Polygon()
    b = c.bounds
    final = c.intersection(box(b[2] - p.cable_largo * 2, b[1], b[2], b[3]))
    centro = polylabel(max(_poligonos(final) or _poligonos(c), key=lambda q: q.area), tolerance=0.3)
    return box(centro.x - p.cable_largo / 2, centro.y - p.cable_ancho / 2,
               centro.x + p.cable_largo / 2, centro.y + p.cable_ancho / 2).intersection(c.buffer(-0.6))


def _gramos(m: Manifold, cascara=0.85, relleno=0.15) -> float:
    """Peso aproximado ya impreso: cascara (paredes y tapas) + relleno."""
    v_cascara = min(m.surface_area() * cascara, m.volume())
    return (v_cascara + (m.volume() - v_cascara) * relleno) / 1000 * DENSIDAD_PETG


def construir(d: dict, p: Perfil):
    """Arma en 3D cada pieza (carcasa) y su cubierta."""
    salida = []
    for i, t in enumerate(d["piezas"], 1):
        w, caja = t["palabra"], t["caja"]
        contorno = t["contorno"]
        canal = w["canal"].intersection(caja)
        alojamiento = w["canal"].buffer(p.escalon).intersection(caja)
        tunel = w["tuneles"].intersection(caja)
        carcasa = _prisma(contorno, 0, p.profundidad)
        huecos = [_prisma(canal, p.base, p.fondo_canal + 0.01),
                  _prisma(alojamiento, p.fondo_canal, p.profundidad + 1),
                  _prisma(tunel, p.base, p.base + p.alto_tunel),
                  _prisma(_colgador(contorno, p), -1, p.base + 0.01)]
        if t.get("cable"):
            huecos.append(_prisma(_cable(w["canal"], caja, p), -1, p.base + 0.01))
        carcasa = carcasa - Manifold.batch_boolean([h for h in huecos if not h.is_empty()], OpType.Add)
        ext = w["canal"].buffer(p.escalon - p.tapa_holgura)
        inter = w["canal"].buffer(p.escalon - p.tapa_holgura - p.tapa_pared)
        cubierta = (_prisma(ext.intersection(caja), p.fondo_canal, p.profundidad)
                    - _prisma(inter.intersection(caja), p.fondo_canal + p.tapa_frente, p.profundidad + 1))
        salida.append({"n": i, "carcasa": carcasa, "cubierta": cubierta, "contorno": contorno})
    return salida


def vista_previa(d: dict, ruta, escala=2.0):
    """Vista de frente: canal encendido, contorno y lineas de corte."""
    todo = unary_union([w["contorno"] for w in d["palabras"]])
    x0, y0, x1, y1 = todo.bounds
    m = 20
    W, H = int((x1 - x0) * escala + 2 * m), int((y1 - y0) * escala + 2 * m)
    img = Image.new("RGB", (W, H), (22, 22, 26))
    dib = ImageDraw.Draw(img)
    tx = lambda xy: [((x - x0) * escala + m, H - ((y - y0) * escala + m)) for x, y in xy]  # noqa: E731

    def pinta(g, color, borde=None):
        for q in _poligonos(g):
            dib.polygon(tx(q.exterior.coords), fill=color, outline=borde)
            for r in q.interiors:
                dib.polygon(tx(r.coords), fill=(22, 22, 26))

    for w in d["palabras"]:
        pinta(w["contorno"], (60, 60, 66))
        pinta(w["canal"].buffer(2), (255, 190, 120))  # brillo
        pinta(w["canal"], (255, 238, 210))
        pinta(w["tuneles"].difference(w["canal"]), (130, 110, 90))
    for t in d["piezas"][:-1]:
        x = t["caja"].bounds[2]
        dib.line(tx([(x, y0 - 3), (x, y1 + 3)]), fill=(90, 160, 255), width=2)
    img.save(ruta, "PNG")


def generar(texto: str, fuente: str, altura: float, perfil: Perfil, carpeta: Path) -> dict:
    d = disenar(texto, fuente, altura, perfil)
    piezas = construir(d, perfil)
    zip_ruta = carpeta / "letrero.zip"
    gramos = 0.0
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for pz in piezas:
            z.writestr(f"pieza{pz['n']:02d}_carcasa.stl", stl_bytes(pz["carcasa"]))
            z.writestr(f"pieza{pz['n']:02d}_cubierta.stl", stl_bytes(pz["cubierta"]))
            gramos += sum(_gramos(m) for m in (pz["carcasa"], pz["cubierta"]))
        z.writestr("perfil.txt", "\n".join(f"{k}: {v}" for k, v in asdict(perfil).items()))
    vista_previa(d, carpeta / "previa.png")
    todo = unary_union([w["contorno"] for w in d["palabras"]]).bounds
    medidas = [(round(pz["contorno"].bounds[2] - pz["contorno"].bounds[0]),
                round(pz["contorno"].bounds[3] - pz["contorno"].bounds[1])) for pz in piezas]
    return {"medidas": f"{todo[2] - todo[0]:.0f} x {todo[3] - todo[1]:.0f} x {perfil.profundidad:g} mm",
            "piezas": len(piezas), "medidas_piezas": [f"{a} x {b}" for a, b in medidas],
            "gramos": round(gramos), "advertencias": d["advertencias"], "perfil": asdict(perfil)}


def ensayo_png(texto: str, fuente: str, altura: float, perfil: Perfil) -> bytes:
    """Vista previa rapida (solo 2D) para probar texto, fuente y tamano."""
    buf = io.BytesIO()
    vista_previa(disenar(texto, fuente, altura, perfil), buf, escala=1.0)
    return buf.getvalue()
