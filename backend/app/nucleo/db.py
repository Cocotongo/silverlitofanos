"""Base de datos y carpetas de archivos."""
import os
from pathlib import Path

from sqlmodel import Session, create_engine

DATOS = Path(os.environ.get("SILVER_DATOS", Path(__file__).resolve().parents[2] / "datos"))
ARCHIVOS = DATOS / "pedidos"
ARCHIVOS.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DATOS / 'pedidos.db'}", connect_args={"check_same_thread": False})


def sesion():
    with Session(engine) as s:
        yield s
