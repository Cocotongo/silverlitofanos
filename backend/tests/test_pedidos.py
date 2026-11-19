import io
import json
import os
import tempfile

os.environ["SILVER_DATOS"] = tempfile.mkdtemp()

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402

cliente = TestClient(app)


def foto_prueba():
    img = Image.new("L", (300, 200), 255)
    for x in range(300):
        for y in range(80, 120):
            img.putpixel((x, y), x * 255 // 300)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    buf.seek(0)
    return buf


def crear(producto="panel-100", **config):
    r = cliente.post("/api/pedidos", data={"cliente": "Ana López", "telefono": "8112345678", "linea": "litofano",
                                           "producto": producto, "config": json.dumps({"material": "petg", **config})},
                     files={"archivo": ("foto.jpg", foto_prueba(), "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()


def test_lineas():
    lineas = cliente.get("/api/lineas").json()
    lito = next(l for l in lineas if l["id"] == "litofano")
    assert [p["id"] for p in lito["flujo"]][:2] == ["nuevo", "previa_enviada"]
    assert {p["fase"] for p in lito["flujo"]} >= {"nuevo", "produccion", "entregado", "cancelado"}
    assert lito["archivo"]["acepta"] == "image/*"
    assert all(p["linea"] == "litofano" for p in cliente.get("/api/productos").json())


def test_flujo_panel():
    p = crear()
    assert p["estado"] == "nuevo" and p["precio"] == 399 and p["linea"] == "litofano"
    assert p["config"]["forma"] == "panel" and p["config"]["ancho"] == 100 and p["config"]["material"] == "petg"
    assert cliente.get(f"/api/pedidos/{p['id']}/archivo").status_code == 200
    assert cliente.get(f"/api/pedidos/{p['id']}/descarga").status_code == 404

    g = cliente.post(f"/api/pedidos/{p['id']}/generar").json()
    assert g["generado"] and g["resumen"]["gramos"] > 0 and g["resumen"]["medidas"].startswith("106 x")
    assert cliente.get(f"/api/pedidos/{p['id']}/previa").headers["content-type"] == "image/png"
    z = cliente.get(f"/api/pedidos/{p['id']}/descarga")
    assert z.status_code == 200 and z.content[:2] == b"PK"

    a = cliente.patch(f"/api/pedidos/{p['id']}", json={"estado": "imprimiendo", "anticipo": 200}).json()
    assert a["estado"] == "imprimiendo" and a["anticipo"] == 200 and a["generado"]
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"material": "petg"}}).json()["generado"]
    b = cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"material": "pla"}}).json()
    assert b["generado"] is False and b["config"]["material"] == "pla" and b["config"]["ancho"] == 100

    assert any(x["id"] == p["id"] for x in cliente.get("/api/pedidos?estado=imprimiendo").json())
    assert cliente.get("/api/pedidos?linea=letreros").json() == []
    assert cliente.delete(f"/api/pedidos/{p['id']}").status_code == 204
    assert cliente.get(f"/api/pedidos/{p['id']}").status_code == 404


def test_cilindro_genera():
    p = crear("cilindro-80")
    g = cliente.post(f"/api/pedidos/{p['id']}/generar").json()
    assert g["generado"] and g["resumen"]["medidas"] == "Ø80 x 100 mm"


def test_validaciones():
    foto = lambda: {"archivo": ("f.jpg", foto_prueba(), "image/jpeg")}  # noqa: E731
    assert cliente.post("/api/pedidos", data={"cliente": "X", "producto": "nada"}, files=foto()).status_code == 400
    assert cliente.post("/api/pedidos", data={"cliente": "X", "linea": "nada", "producto": "panel-100"},
                        files=foto()).status_code == 400
    r = cliente.post("/api/pedidos", data={"cliente": "X", "producto": "panel-100"},
                     files={"archivo": ("f.txt", io.BytesIO(b"hola"), "text/plain")})
    assert r.status_code == 400
    assert cliente.post("/api/pedidos", data={"cliente": "X", "producto": "panel-100"}).status_code == 400
    r = cliente.post("/api/pedidos", data={"cliente": "X", "producto": "panel-100",
                                           "config": json.dumps({"material": "madera"})}, files=foto())
    assert r.status_code == 422
    p = crear()
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"estado": "volando"}).status_code == 422


def test_encuadre_y_ensayo():
    p = crear()
    assert p["config"]["zoom"] == 1 and p["config"]["mejorar"] is True
    cliente.post(f"/api/pedidos/{p['id']}/generar")
    url = f"/api/lineas/litofano/pedidos/{p['id']}/ensayo"
    r = cliente.get(url, params={"x": 0.3, "y": 0.6, "zoom": 2, "mejorar": False})
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert cliente.get(url, params={"zoom": 9}).status_code == 422

    a = cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"encuadre_x": 0.3, "zoom": 2}}).json()
    assert a["config"]["encuadre_x"] == 0.3 and a["config"]["zoom"] == 2 and a["generado"] is False
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"zoom": 0.5}}).status_code == 422
    assert cliente.post(f"/api/pedidos/{p['id']}/generar").json()["generado"]


def test_migra_pedidos_de_la_version_anterior():
    from sqlalchemy import create_engine, text

    from app.nucleo.migracion import iniciar

    engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/v1.db")
    with engine.begin() as con:
        con.execute(text(
            "CREATE TABLE pedido (id INTEGER PRIMARY KEY, cliente VARCHAR NOT NULL, telefono VARCHAR NOT NULL, "
            "canal VARCHAR NOT NULL, producto VARCHAR NOT NULL, forma VARCHAR NOT NULL, material VARCHAR NOT NULL, "
            "ancho FLOAT NOT NULL, diametro FLOAT NOT NULL, alto FLOAT NOT NULL, precio FLOAT NOT NULL, "
            "anticipo FLOAT NOT NULL, estado VARCHAR NOT NULL, notas VARCHAR NOT NULL, fecha_entrega DATE, "
            "creado DATETIME NOT NULL, carpeta VARCHAR NOT NULL, foto_nombre VARCHAR NOT NULL, "
            "stl_listo BOOLEAN NOT NULL, gramos FLOAT, medidas VARCHAR NOT NULL, encuadre_x FLOAT DEFAULT 0.5, "
            "encuadre_y FLOAT DEFAULT 0.5, zoom FLOAT DEFAULT 1.0, mejorar BOOLEAN DEFAULT 1)"))
        con.execute(text(
            "INSERT INTO pedido VALUES (7, 'Luis', '81', 'WhatsApp', 'cilindro-80', 'cilindro', 'pla', 150, 80, 100, "
            "649, 300, 'aprobado', 'nota', '2026-12-01', '2026-11-01 10:00:00', 'abc', 'foto.jpg', 1, 61.5, "
            "'Ø80 x 100 mm', 0.4, 0.5, 1.5, 0)"))
    iniciar(engine)
    iniciar(engine)  # correrla otra vez no hace nada
    with engine.connect() as con:
        f = con.execute(text("SELECT * FROM pedido")).mappings().one()
    assert f["id"] == 7 and f["linea"] == "litofano" and f["estado"] == "aprobado" and f["archivo"] == "foto.jpg"
    assert f["generado"] and json.loads(f["resumen"]) == {"gramos": 61.5, "medidas": "Ø80 x 100 mm"}
    assert json.loads(f["config"]) == {"forma": "cilindro", "material": "pla", "ancho": 150, "diametro": 80,
                                       "alto": 100, "encuadre_x": 0.4, "encuadre_y": 0.5, "zoom": 1.5,
                                       "mejorar": False}


def test_encuadrar_y_clahe():
    import numpy as np

    from app.lineas.litofano import generador as litofano

    img = Image.new("L", (400, 200))
    img.paste(255, (0, 0, 100, 200))  # franja blanca a la izquierda
    # sin zoom y centrado = recorte central de siempre
    centro = np.asarray(litofano.encuadrar(img, 100, 100))
    assert centro.mean() < 10
    izquierda = np.asarray(litofano.encuadrar(img, 100, 100, x=0.0))
    assert izquierda[:, :40].mean() > 245
    # zoom al centro de la franja: todo blanco
    assert np.asarray(litofano.encuadrar(img, 50, 50, x=0.125, zoom=4)).min() > 245

    # CLAHE resalta el detalle fino de una foto apagada
    gris = (120 + np.random.default_rng(0).integers(-6, 7, (90, 120))).astype(np.uint8)
    mejor = litofano.clahe(gris)
    assert mejor.shape == gris.shape and mejor.dtype == np.uint8
    assert mejor.std() > 2 * gris.std()
