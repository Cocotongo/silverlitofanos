"""Versión de SilVer: número = commits de main (sube con cada PR fusionado), commit corto y fecha.

Se lee de git. En Docker la imagen no lleva .git, así que se toma de version.json,
que escribe tools/actualizar_servidor.sh antes de reconstruir.
"""
import json
import subprocess
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

BACKEND = Path(__file__).resolve().parents[1]
ARCHIVO = BACKEND / "version.json"

router = APIRouter()


def _desde_git():
    try:
        salida = subprocess.run(
            ["git", "log", "-1", "--format=%h|%cd", "--date=format:%Y-%m-%d %H:%M"],
            cwd=BACKEND, capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        numero = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=BACKEND, capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    commit, fecha = salida.split("|", 1)
    return {"version": int(numero), "commit": commit, "fecha": fecha}


def _desde_archivo(archivo: Path):
    try:
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        return {"version": int(datos["version"]), "commit": str(datos["commit"]), "fecha": str(datos["fecha"])}
    except (OSError, ValueError, KeyError, TypeError):
        return None


@lru_cache
def version_app():
    return _desde_git() or _desde_archivo(ARCHIVO) or {"version": None, "commit": None, "fecha": None}


@router.get("/api/version")
def obtener_version():
    return version_app()
