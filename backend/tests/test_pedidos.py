import io
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


def crear(producto="panel-100"):
    r = cliente.post("/api/pedidos", data={"cliente": "Ana López", "telefono": "8112345678",
                                           "producto": producto, "material": "petg"},
                     files={"foto": ("foto.jpg", foto_prueba(), "image/jpeg")})
    assert r.status_code == 201, r.text
    return r.json()


def test_flujo_panel():
    p = crear()
    assert p["estado"] == "nuevo" and p["precio"] == 399 and p["forma"] == "panel"
    assert cliente.get(f"/api/pedidos/{p['id']}/foto").status_code == 200
    assert cliente.get(f"/api/pedidos/{p['id']}/stl").status_code == 404

    g = cliente.post(f"/api/pedidos/{p['id']}/generar").json()
    assert g["stl_listo"] and g["gramos"] > 0 and g["medidas"].startswith("106 x")
    assert cliente.get(f"/api/pedidos/{p['id']}/previa").headers["content-type"] == "image/png"
    z = cliente.get(f"/api/pedidos/{p['id']}/stl")
    assert z.status_code == 200 and z.content[:2] == b"PK"

    a = cliente.patch(f"/api/pedidos/{p['id']}", json={"estado": "imprimiendo", "anticipo": 200}).json()
    assert a["estado"] == "imprimiendo" and a["anticipo"] == 200 and a["stl_listo"]
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"material": "pla"}).json()["stl_listo"] is False

    assert any(x["id"] == p["id"] for x in cliente.get("/api/pedidos?estado=imprimiendo").json())
    assert cliente.delete(f"/api/pedidos/{p['id']}").status_code == 204
    assert cliente.get(f"/api/pedidos/{p['id']}").status_code == 404


def test_cilindro_genera():
    p = crear("cilindro-80")
    g = cliente.post(f"/api/pedidos/{p['id']}/generar").json()
    assert g["stl_listo"] and g["medidas"] == "Ø80 x 100 mm"


def test_validaciones():
    r = cliente.post("/api/pedidos", data={"cliente": "X", "producto": "nada"},
                     files={"foto": ("f.jpg", foto_prueba(), "image/jpeg")})
    assert r.status_code == 400
    r = cliente.post("/api/pedidos", data={"cliente": "X"},
                     files={"foto": ("f.txt", io.BytesIO(b"hola"), "text/plain")})
    assert r.status_code == 400


def test_encuadre_y_ensayo():
    p = crear()
    assert p["zoom"] == 1 and p["mejorar"] is True
    cliente.post(f"/api/pedidos/{p['id']}/generar")
    r = cliente.get(f"/api/pedidos/{p['id']}/ensayo", params={"x": 0.3, "y": 0.6, "zoom": 2, "mejorar": False})
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert cliente.get(f"/api/pedidos/{p['id']}/ensayo", params={"zoom": 9}).status_code == 422

    a = cliente.patch(f"/api/pedidos/{p['id']}", json={"encuadre_x": 0.3, "zoom": 2}).json()
    assert a["encuadre_x"] == 0.3 and a["zoom"] == 2 and a["stl_listo"] is False
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"zoom": 0.5}).status_code == 422
    assert cliente.post(f"/api/pedidos/{p['id']}/generar").json()["stl_listo"]


def test_encuadrar_y_clahe():
    import numpy as np
    from app import litofano

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
