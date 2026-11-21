import json
import os
import tempfile

os.environ.setdefault("SILVER_DATOS", tempfile.mkdtemp())

from app import version  # noqa: E402


def test_desde_git():
    v = version._desde_git()
    assert v is not None
    assert v["version"] > 0 and len(v["commit"]) >= 7


def test_desde_archivo(tmp_path):
    archivo = tmp_path / "version.json"
    archivo.write_text(json.dumps({"version": 12, "commit": "abc1234", "fecha": "2026-11-20 18:00"}))
    assert version._desde_archivo(archivo) == {"version": 12, "commit": "abc1234", "fecha": "2026-11-20 18:00"}


def test_archivo_faltante_o_roto(tmp_path):
    assert version._desde_archivo(tmp_path / "no.json") is None
    roto = tmp_path / "roto.json"
    roto.write_text("{")
    assert version._desde_archivo(roto) is None


def test_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).get("/api/version")
    assert r.status_code == 200
    assert set(r.json()) == {"version", "commit", "fecha"}
