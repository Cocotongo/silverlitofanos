"""Registro de lineas de producto."""
from fastapi import HTTPException

from .base import Linea
from .letrero import Letrero
from .litofano import Litofano

LINEAS: dict[str, Linea] = {l.id: l for l in (Litofano(), Letrero())}


def linea(linea_id: str) -> Linea:
    if linea_id not in LINEAS:
        raise HTTPException(400, f"Línea de producto desconocida: {linea_id}")
    return LINEAS[linea_id]
