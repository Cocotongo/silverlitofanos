import os
import tempfile

os.environ.setdefault("SILVER_DATOS", tempfile.mkdtemp())

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.lineas.luna import generador  # noqa: E402
from app.main import app  # noqa: E402

cliente = TestClient(app)


def test_esfera_cerrada_y_con_boca(tmp_path):
    esp, theta, phi, r_in, alfa0 = generador.espesores(diametro=80, abertura=30, resolucion=1.5)
    v, caras = generador.esfera(esp, theta, phi, r_in, alfa0)
    # cada arista la comparten exactamente dos triangulos, en sentidos opuestos (solido cerrado)
    aristas = np.concatenate([caras[:, [0, 1]], caras[:, [1, 2]], caras[:, [2, 0]]])
    unicas, cuenta = np.unique(np.sort(aristas, axis=1), axis=0, return_counts=True)
    assert (cuenta == 2).all()
    assert len(np.unique(aristas, axis=0)) == len(aristas)
    # boca plana abajo, del diametro pedido
    abajo = v[np.isclose(v[:, 2], v[:, 2].min())]
    radios = np.hypot(abajo[:, 0], abajo[:, 1])
    assert abs(radios.min() - 15) < 0.01 and radios.max() < 40
    # espesores dentro del rango del PLA, y anillo solido junto a la boca
    assert esp.min() >= 0.8 - 1e-9 and esp.max() <= 3.0 + 1e-9
    assert np.allclose(esp[-1], 3.0)


def test_cara_visible_al_frente(tmp_path):
    # la cara visible de la Luna (mares oscuros = mas gruesos) mira a -Y; la cara oculta es mas clara
    esp, theta, phi, *_ = generador.espesores(diametro=100, resolucion=1.0)
    ecuador = np.argmin(abs(theta - np.pi / 2))
    frente = esp[ecuador, np.argmin(abs(phi - 3 * np.pi / 2))]
    atras = esp[ecuador, np.argmin(abs(phi - np.pi / 2))]
    assert frente > atras


def test_pedido_de_luna_sin_foto():
    r = cliente.post("/api/pedidos", data={"cliente": "Caro", "linea": "luna", "producto": "luna-100",
                                           "config": '{"abertura": 35}'})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["precio"] == 499 and p["config"] == {"material": "pla", "diametro": 100, "abertura": 35}
    g = cliente.post(f"/api/pedidos/{p['id']}/generar").json()
    assert g["generado"] and g["resumen"]["medidas"].startswith("Ø100") and 40 < g["resumen"]["gramos"] < 120
    assert cliente.get(f"/api/pedidos/{p['id']}/previa").headers["content-type"] == "image/png"
    z = cliente.get(f"/api/pedidos/{p['id']}/descarga")
    assert z.status_code == 200 and z.content[:2] == b"PK"
    assert cliente.patch(f"/api/pedidos/{p['id']}", json={"config": {"abertura": 5}}).status_code == 422
