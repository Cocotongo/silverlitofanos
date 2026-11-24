"""Modelos comunes a todas las lineas de producto: el pedido y sus fases."""
import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Fase(str, Enum):
    """Fases generales por las que pasa cualquier pedido, sin importar la linea.

    Cada linea define sus propios pasos (estados) y dice a que fase pertenece cada uno,
    asi se puede ver un tablero unico de todo lo pendiente.
    """
    nuevo = "nuevo"
    diseno = "diseno"
    aprobado = "aprobado"
    produccion = "produccion"
    listo = "listo"
    entregado = "entregado"
    cancelado = "cancelado"


class Pedido(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    linea: str = "litofano"
    cliente: str
    telefono: str = ""
    canal: str = "WhatsApp"
    producto: str = ""
    precio: float = 0
    anticipo: float = 0
    estado: str = "nuevo"  # uno de los pasos del flujo de su linea
    notas: str = ""
    fecha_entrega: Optional[date] = None
    creado: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    carpeta: str = Field(default_factory=lambda: uuid.uuid4().hex)
    archivo: str = ""  # nombre del archivo que mando el cliente (foto, logo, dxf...)
    # todos los archivos del cliente, en orden, cuando la linea pide varios (p. ej. las 4 fotos del cubo)
    archivos: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]"))
    # datos propios de la linea (p. ej. forma, material y encuadre del litofano)
    config: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    generado: bool = False  # ya se generaron los archivos de produccion
    resumen: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class PedidoCambios(SQLModel):
    cliente: Optional[str] = None
    telefono: Optional[str] = None
    canal: Optional[str] = None
    precio: Optional[float] = None
    anticipo: Optional[float] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    fecha_entrega: Optional[date] = None
    config: Optional[dict[str, Any]] = None  # cambios parciales; se validan con la linea
