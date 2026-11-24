import io
import os
import tempfile
import zipfile

os.environ.setdefault("SILVER_DATOS", tempfile.mkdtemp())

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from manifold3d import Manifold, Mesh, OpType  # noqa: E402
from PIL import Image  # noqa: E402

from app.lineas.cubo import generador  # noqa: E402
from app.main import app  # noqa: E402

cliente = TestClient(app)


def foto(tono):
    buf = io.BytesIO()
    Image.new("L", (200, 160), tono).save(buf, "JPEG")
    buf.seek(0)
    return buf


def fotos(n):
    return [("archivos", (f"f{i}.jpg", foto(40 * i), "image/jpeg")) for i in range(n)]


def crear(n=4, **extra):
    return cliente.post("/api/pedidos", data={"cliente": "Dani", "linea": "cubo", "producto": "cubo-80", **extra},
                        files=fotos(n))


def test_pedido_con_4_fotos():
    lineas = {l["id"]: l for l in cliente.get("/api/lineas").json()}
    assert lineas["cubo"]["archivo"]["cantidad"] == 4 and lineas["litofano"]["archivo"]["cantidad"] == 1
    assert crear(3).status_code == 400
    assert crear(5).status_code == 400
    r = crear()
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["archivos"] == [f"original_{i}.jpg" for i in range(1, 5)] and p["archivo"] == "original_1.jpg"
    assert p["precio"] == 999 and len(p["config"]["encuadres"]) == 4
    assert cliente.get(f"/api/pedidos/{p['id']}/archivo", params={"n": 3}).status_code == 200
    assert cliente.get(f"/api/pedidos/{p['id']}/archivo", params={"n": 5}).status_code == 404

    e = cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"encuadres": [{"zoom": 2}] * 4}}).json()
    assert e["config"]["encuadres"][0] == {"x": 0.5, "y": 0.5, "zoom": 2}
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"encuadres": [{}] * 3}}).status_code == 422

    g = cliente.post(f"/api/pedidos/{p['id']}/generar").json()
    assert g["generado"] and g["resumen"]["medidas"].startswith("89 x 89") and g["resumen"]["gramos"] > 30
    z = zipfile.ZipFile(io.BytesIO(cliente.get(f"/api/pedidos/{p['id']}/descarga").content))
    nombres = sorted(z.namelist())
    assert len([n for n in nombres if n.endswith(".stl")]) == 6 and "LEEME.txt" in nombres


def test_un_solo_archivo_sigue_igual():
    r = cliente.post("/api/pedidos", data={"cliente": "Eva", "linea": "litofano", "producto": "panel-100"},
                     files={"archivo": ("a.jpg", foto(100), "image/jpeg")})
    assert r.status_code == 201 and r.json()["archivos"] == ["original.jpg"]


def _manifold(v, f):
    tri = v[f]
    if np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum() < 0:
        f = f[:, ::-1]
    return Manifold(Mesh(vert_properties=np.asarray(v, np.float32), tri_verts=np.asarray(f, np.uint32)))


def test_caras_embonan_en_base_y_tapa(tmp_path):
    Image.new("L", (100, 100), 128).save(tmp_path / "f.png")
    m = generador.medidas(80, "pla")
    L = m["lado"]
    esp = generador.espesores_cara(str(tmp_path / "f.png"), m, resolucion=1.0)
    cara = _manifold(*generador.cara(esp, m))
    caras = [cara.translate((-L / 2, -L / 2, 0)).rotate((0, 0, 90 * i)) for i in range(4)]
    anillo = Manifold.batch_boolean(caras, OpType.Add)
    # las 4 caras se tocan en las esquinas a 45 grados sin encimarse y forman un anillo cerrado
    assert abs(anillo.volume() - sum(c.volume() for c in caras)) < 1e-3 and anillo.genus() == 1
    z = m["alto_base"] - m["ranura"]
    assert (generador.base(m) ^ anillo.translate((0, 0, z))).volume() < 1e-3
    assert (generador.tapa(m).translate((0, 0, z + L - m["ranura"])) ^ anillo.translate((0, 0, z))).volume() < 1e-3
