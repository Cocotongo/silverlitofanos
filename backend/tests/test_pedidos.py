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
