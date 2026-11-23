"""Registro de lineas de producto."""
from fastapi import HTTPException

from .base import Linea
from .letrero import Letrero
from .litofano import Litofano
from .luna import Luna

LINEAS: dict[str, Linea] = {l.id: l for l in (Litofano(), Letrero(), Luna())}


def linea(linea_id: str) -> Linea:
    if linea_id not in LINEAS:
        raise HTTPException(400, f"Línea de producto desconocida: {linea_id}")
    return LINEAS[linea_id]
