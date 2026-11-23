"""Linea de producto: lamparas luna (esfera litofano con la superficie lunar, sin foto del cliente)."""
import zipfile
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from ...nucleo.modelos import Fase, Pedido
from ..base import Linea, Paso
from . import generador


class Material(str, Enum):
    pla = "pla"
    petg = "petg"


class ConfigLuna(BaseModel):
    material: Material = Material.pla
    diametro: float = Field(150, ge=60, le=200)   # cabe en la cama de la Ender-3 V3 KE
    abertura: float = Field(40, ge=15, le=80)     # boca para la placa LED (medirla al comprar)


class Luna(Linea):
    id = "luna"
    nombre = "Lámparas luna"
    Config = ConfigLuna
    productos = [
        {"id": "luna-150", "nombre": "Lámpara luna Ø150 mm", "precio": 699, "config": {"diametro": 150}},
        {"id": "luna-100", "nombre": "Lámpara luna Ø100 mm", "precio": 499, "config": {"diametro": 100}},
    ]
    flujo = [
        Paso("nuevo", "Nuevo", Fase.nuevo),
        Paso("aprobado", "Aprobado", Fase.aprobado),
        Paso("imprimiendo", "Imprimiendo", Fase.produccion),
        Paso("listo", "Listo para entregar", Fase.listo),
        Paso("entregado", "Entregado", Fase.entregado),
        Paso("cancelado", "Cancelado", Fase.cancelado),
    ]
    archivo = None  # no lleva foto del cliente
    descarga = "luna.zip"

    def generar(self, pedido: Pedido, carpeta: Path) -> dict:
        c = ConfigLuna(**pedido.config)
        stl = carpeta / "luna.stl"
        r = generador.generar(str(stl), c.diametro, c.abertura, c.material.value, previa=str(carpeta / "previa.png"))
        with zipfile.ZipFile(carpeta / self.descarga, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(stl, f"pedido{pedido.id}_luna_{c.diametro:.0f}mm_{c.material.value}.stl")
        stl.unlink()
        return {"gramos": r["gramos"], "medidas": r["medidas"]}
