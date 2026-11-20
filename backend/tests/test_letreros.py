import io
import os
import tempfile
import zipfile

os.environ.setdefault("SILVER_DATOS", tempfile.mkdtemp())

from fastapi.testclient import TestClient  # noqa: E402

from app.lineas.letrero import generador  # noqa: E402
from app.main import app  # noqa: E402

cliente = TestClient(app)


def test_perfiles_editables():
    perfiles = cliente.get("/api/lineas/letrero/perfiles").json()
    assert perfiles and perfiles[0]["ancho_tira"] == 10 and perfiles[0]["alto_tunel"] == 13
    assert perfiles[0]["holgura_union"] == 0.2
    nuevo = cliente.post("/api/lineas/letrero/perfiles", json={"nombre": "Tira 8 mm", "proveedor": "X",
                                                               "ancho_tira": 8}).json()
    assert nuevo["ancho_tira"] == 8 and nuevo["pared"] == 9.2
    e = cliente.patch(f"/api/lineas/letrero/perfiles/{nuevo['id']}", json={"alto_tunel": 11}).json()
    assert e["alto_tunel"] == 11 and e["ancho_tira"] == 8
    assert cliente.patch(f"/api/lineas/letrero/perfiles/{nuevo['id']}", json={"ancho_tira": -1}).status_code == 422
    assert cliente.post("/api/lineas/letrero/perfiles", json={"ancho_tira": 8}).status_code == 422
    assert cliente.delete(f"/api/lineas/letrero/perfiles/{nuevo['id']}").status_code == 204


def test_pedido_de_letrero():
    assert "Pacifico-Regular" in cliente.get("/api/lineas/letrero/fuentes").json()
    r = cliente.post("/api/pedidos", data={"cliente": "Bea", "linea": "letrero", "producto": "letrero-chico",
                                           "config": '{"texto": "Hola Ana", "fuente": "Pacifico-Regular"}'})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["estado"] == "nuevo" and p["config"]["altura"] == 90 and p["archivo"] == ""
    assert cliente.get("/api/lineas/letrero/ensayo", params={"texto": "Hola Ana"}).content[:4] == b"\x89PNG"

    g = cliente.post(f"/api/pedidos/{p['id']}/generar").json()
    assert g["generado"] and g["resumen"]["piezas"] >= 2 and g["resumen"]["perfil"]["ancho_tira"] == 10
    z = zipfile.ZipFile(io.BytesIO(cliente.get(f"/api/pedidos/{p['id']}/descarga").content))
    nombres = z.namelist()
    assert "pieza01_carcasa.stl" in nombres and "pieza01_cubierta.stl" in nombres and "perfil.txt" in nombres

    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"estado": "armando"}).json()["estado"] == "armando"
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"fuente": "Comic"}}).status_code == 422
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"texto": "Hola"}}).json()["generado"] is False


def test_geometria():
    p = generador.Perfil()
    d = generador.disenar("Pretty Cutters", "Lobster-Regular", 120, p)
    # ninguna pieza pasa de la cama y entre piezas queda la holgura
    for t in d["piezas"]:
        b = t["contorno"].bounds
        assert b[2] - b[0] <= p.pieza_max and b[3] - b[1] <= p.pieza_max
    for a, b in zip(d["piezas"], d["piezas"][1:]):
        if a["palabra"] is b["palabra"]:
            assert abs(b["caja"].bounds[0] - a["caja"].bounds[2] - p.holgura_union) < 1e-6
    # P y r no se tocan: tunel del ancho de la tira + holgura
    t = d["palabras"][0]["tuneles"]
    assert not t.is_empty and t.minimum_rotated_rectangle.length > 0
    piezas = generador.construir(d, p)
    for pz in piezas:
        assert pz["carcasa"].status().name == "NoError" and pz["carcasa"].volume() > 0
        assert abs(pz["cubierta"].bounding_box()[5] - pz["cubierta"].bounding_box()[2] - 20) < 1e-6
    # la cubierta entra en el alojamiento con su holgura
    assert abs(p.escalon - p.tapa_holgura - p.tapa_pared) < 1e-9


def test_tira_mas_ancha_avisa():
    ancha = generador.Perfil(ancho_tira=20)
    assert generador.disenar("Hola", "Pacifico-Regular", 60, ancha)["advertencias"]
