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


@pytest.mark.parametrize("diametro,cuantas", [(300, (4, 4, 4)), (410, (4, 4, 4)), (600, (16, 16, 12))])
def test_piezas_caben_y_no_chocan(diametro, cuantas):
    m = g.medidas(diametro)
    assert tuple(g.piezas_por_tipo(m).values()) == cuantas
    armada = g.armada(m, resolucion=3.0)
    todas = []
    for tipo, piezas in armada.items():
        for pieza, medio, abarca in piezas:
            x0, y0, z0, x1, y1, z1 = g.para_imprimir(pieza, medio, abarca).bounding_box()
            assert x1 - x0 <= g.UTIL and y1 - y0 <= g.UTIL, (tipo, x1 - x0, y1 - y0)
            assert pieza.volume() > 1
            todas.append(pieza)
    for i in range(len(todas)):
        for j in range(i + 1, len(todas)):
            assert (todas[i] ^ todas[j]).volume() < 0.01, (i, j)
    # el relieve queda debajo del labio del aro y el marco asienta en la pestana
    assert max(p.bounding_box()[5] for p, *_ in armada["loseta"]) <= m["alto"] - m["labio"] - 2 + 1e-6
    assert min(p.bounding_box()[2] for p, *_ in armada["marco"]) == pytest.approx(m["piso"])
    # las losetas cubren el disco (menos las juntas)
    area = sum(p.volume() for p, *_ in armada["loseta"]) / (m["base"] + 0.5 * m["alto_relieve"])
    assert area == pytest.approx(np.pi * m["R"] ** 2, rel=0.08)


def test_colas_de_milano_entran_en_la_pieza_vecina():
    # si la cola entra y no choca (prueba de arriba), la pieza vecina tiene su hueco
    m = g.medidas(600)
    borde = g.marco_2d(m)["borde"]
    centro = g.Manifold.cylinder(20, borde, borde, 720).translate([0, 0, -5])
    piezas = g.piezas_marco(m)
    for p, medio, abarca in piezas[4:]:                    # anillo de afuera: cola hacia el centro
        assert (p ^ centro).volume() > 20
    for p, medio, abarca in piezas[:4]:                    # cuartos: cola mas alla de su cuña
        a1 = medio + abarca / 2
        tapa = g.Manifold.extrude(g._cuña(a1, a1 + 0.3, borde), 20).translate([0, 0, -5])
        assert (p ^ tapa).volume() > 20


def test_no_cabe_mas_grande():
    with pytest.raises(ValueError):
        g.medidas(800)


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
    assert len([n for n in nombres if n.endswith(".stl")]) == 12 and gen["resumen"]["losetas"] == 4 and "LEEME.txt" in nombres
    assert any("loseta01_blanco" in n for n in nombres) and any("aro03_negro" in n for n in nombres)
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"diametro": 700}}).status_code == 422


def test_producto_de_60_cm():
    r = cliente.post("/api/pedidos", data={"cliente": "Mau", "linea": "luna_pared", "producto": "luna-pared-60"})
    assert r.status_code == 201, r.text
    assert r.json()["precio"] == 4999 and r.json()["config"]["diametro"] == 600
