"""Contrato que cumple cada linea de producto (litofanos, letreros LED, juguetes...).

Para agregar una linea nueva:
  1. Crea la carpeta app/lineas/<linea>/ con una clase que herede de Linea.
  2. Define su Config (los datos que pide), sus productos, su flujo y como genera los archivos.
  3. Registrala en app/lineas/__init__.py.
El nucleo (pedidos, cobros, fechas, archivos) no se toca.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..nucleo.modelos import Fase, Pedido


@dataclass(frozen=True)
class Paso:
    id: str
    nombre: str
    fase: Fase


@dataclass(frozen=True)
class Archivo:
    """El archivo que manda el cliente al hacer el pedido."""
    etiqueta: str
    acepta: str  # como el atributo accept de <input type=file>, p. ej. "image/*" o ".dxf,.svg"
    requerido: bool = True


class Linea:
    id: ClassVar[str]
    nombre: ClassVar[str]
    Config: ClassVar[type[BaseModel]]
    productos: ClassVar[list[dict[str, Any]]]  # {id, nombre, precio, config: {...}}
    flujo: ClassVar[list[Paso]]
    archivo: ClassVar[Optional[Archivo]] = None
    descarga: ClassVar[str] = "produccion.zip"  # archivo que produce generar(), dentro de la carpeta
    router: ClassVar[Optional[APIRouter]] = None  # rutas extra propias de la linea

    def producto(self, producto_id: str) -> Optional[dict[str, Any]]:
        return next((p for p in self.productos if p["id"] == producto_id), None)

    def config_inicial(self, producto: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
        return self.Config(**{**producto.get("config", {}), **extra}).model_dump(mode="json")

    def actualizar_config(self, actual: dict[str, Any], cambios: dict[str, Any]) -> dict[str, Any]:
        return self.Config(**{**actual, **cambios}).model_dump(mode="json")

    def acepta_archivo(self, nombre: str, tipo: str) -> bool:
        return True

    def generar(self, pedido: Pedido, carpeta: Path) -> dict[str, Any]:
        """Crea los archivos de produccion en la carpeta del pedido y devuelve un resumen."""
        raise NotImplementedError

    def nombre_descarga(self, pedido: Pedido) -> str:
        return f"pedido{pedido.id}_{pedido.cliente.replace(' ', '_')}{Path(self.descarga).suffix}"

    def paso(self, estado: str) -> Optional[Paso]:
        return next((p for p in self.flujo if p.id == estado), None)

    def describir(self) -> dict[str, Any]:
        return {"id": self.id, "nombre": self.nombre, "productos": self.productos,
                "flujo": [{"id": p.id, "nombre": p.nombre, "fase": p.fase.value} for p in self.flujo],
                "archivo": self.archivo and {"etiqueta": self.archivo.etiqueta, "acepta": self.archivo.acepta,
                                             "requerido": self.archivo.requerido}}
