import io
import os
import tempfile
import zipfile

os.environ.setdefault("SILVER_DATOS", tempfile.mkdtemp())

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.lineas.luna_pared import generador as g  # noqa: E402
from app.main import app  # noqa: E402

cliente = TestClient(app)


def _armada(m):
    """Las 12 piezas en su lugar (deshace el giro de impresion)."""
    z0 = m["piso"] + m["marco"]
    losetas = [g.loseta(m, i, 2.0).rotate([0, 0, 90 * i]).translate([0, 0, z0]) for i in range(4)]
    marco = [g.pieza_marco(m, k).rotate([0, 0, 22.5 + 90 * k]).translate([0, 0, m["piso"]]) for k in range(4)]
    aro = [g.pieza_aro(m, k).rotate([0, 0, 45 + 90 * k]) for k in range(4)]
    return losetas, marco, aro


@pytest.mark.parametrize("diametro", [400, 410])
def test_piezas_caben_en_la_cama(diametro):
    m = g.medidas(diametro)
    for k in range(4):
        for pieza in (g.loseta(m, k, 2.0), g.pieza_marco(m, k), g.pieza_aro(m, k)):
            x0, y0, z0, x1, y1, z1 = pieza.bounding_box()
            assert x1 - x0 <= g.CAMA - 4 and y1 - y0 <= g.CAMA - 4 and abs(z0) < 1e-6
            assert pieza.volume() > 0 and pieza.genus() >= 0


def test_no_cabe_mas_grande():
    with pytest.raises(ValueError):
        g.medidas(420)


def test_piezas_armadas_no_chocan():
    m = g.medidas(300)
    losetas, marco, aro = _armada(m)
    todas = losetas + marco + aro
    for i in range(len(todas)):
        for j in range(i + 1, len(todas)):
            assert (todas[i] ^ todas[j]).volume() < 0.01, (i, j)
    # las colas de milano entran en la pieza vecina (sin ellas los aros del marco no llegarian)
    juntas = sum(p.volume() for p in marco)
    assert (marco[0] + marco[1] + marco[2] + marco[3]).volume() == pytest.approx(juntas, rel=1e-6)
    x0, y0, _, x1, y1, _ = g.pieza_marco(m, 0).bounding_box()
    assert x1 - x0 > m["R"]                                  # la cola sobresale de la cuña
    # el relieve queda debajo del labio del aro y el marco asienta en la pestana
    assert max(p.bounding_box()[5] for p in losetas) <= m["alto"] - m["labio"] - 2 + 1e-6
    assert min(p.bounding_box()[2] for p in marco) == pytest.approx(m["piso"])


def test_cara_visible_de_frente():
    # el Mar de la Lluvia (Imbrium, arriba a la izquierda) es mas bajo que las tierras altas del sur
    R = 200.0
    mapa = g._relieve()
    def media(x, y):
        X, Y = np.meshgrid(np.linspace(x - 15, x + 15, 31), np.linspace(y - 15, y + 15, 31))
        return g.alturas(X, Y, R, mapa).mean()
    assert media(0, -150) > media(-50, 100) + 0.05


def test_pedido_de_luna_de_pared():
    r = cliente.post("/api/pedidos", data={"cliente": "Mau", "linea": "luna_pared", "producto": "luna-pared-40",
                                           "config": '{"diametro": 200}'})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["precio"] == 2499 and p["config"] == {"material": "pla", "diametro": 200, "alto_relieve": 5}
    gen = cliente.post(f"/api/pedidos/{p['id']}/generar").json()
    assert gen["generado"] and gen["resumen"]["medidas"].startswith("Ø207")
    assert cliente.get(f"/api/pedidos/{p['id']}/previa").headers["content-type"] == "image/png"
    z = zipfile.ZipFile(io.BytesIO(cliente.get(f"/api/pedidos/{p['id']}/descarga").content))
    nombres = z.namelist()
    assert len([n for n in nombres if n.endswith(".stl")]) == 12 and "LEEME.txt" in nombres
    assert any("loseta1_blanco" in n for n in nombres) and any("aro3_negro" in n for n in nombres)
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"diametro": 500}}).status_code == 422
