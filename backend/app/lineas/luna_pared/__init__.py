"""Linea de producto: luna de pared (cuadro redondo con el relieve lunar y tira LED en el aro)."""
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


class ConfigLunaPared(BaseModel):
    material: Material = Material.pla
    diametro: float = Field(400, ge=200, le=410)        # en 4 piezas por parte, cabe en la cama de la KE
    alto_relieve: float = Field(5, ge=2, le=8)          # cuanto sobresalen los crateres


class LunaPared(Linea):
    id = "luna_pared"
    nombre = "Lunas de pared"
    Config = ConfigLunaPared
    productos = [
        {"id": "luna-pared-40", "nombre": "Luna de pared Ø40 cm", "precio": 2499, "config": {"diametro": 400}},
    ]
    flujo = [
        Paso("nuevo", "Nuevo", Fase.nuevo),
        Paso("aprobado", "Aprobado", Fase.aprobado),
        Paso("imprimiendo", "Imprimiendo", Fase.produccion),
        Paso("armando", "Armando", Fase.produccion),
        Paso("listo", "Listo para entregar", Fase.listo),
        Paso("entregado", "Entregado", Fase.entregado),
        Paso("cancelado", "Cancelado", Fase.cancelado),
    ]
    archivo = None  # no lleva foto del cliente
    descarga = "luna_pared.zip"

    def generar(self, pedido: Pedido, carpeta: Path) -> dict:
        c = ConfigLunaPared(**pedido.config)
        piezas = carpeta / "piezas"
        r = generador.generar(piezas, c.diametro, c.alto_relieve, c.material.value,
                              previa=str(carpeta / "previa.png"))
        colores = {"loseta": "blanco", "marco": "cualquier_color", "aro": "negro"}
        with zipfile.ZipFile(carpeta / self.descarga, "w", zipfile.ZIP_DEFLATED) as z:
            for stl in sorted(piezas.glob("*.stl")):
                color = colores[stl.stem.rstrip("0123456789")]
                z.write(stl, f"pedido{pedido.id}_{stl.stem}_{color}.stl")
                stl.unlink()
            z.writestr("LEEME.txt", LEEME.format(**r, material=c.material.value.upper()))
        piezas.rmdir()
        return r


LEEME = """Luna de pared ({medidas})

Losetas 1-4 ({material} blanco, ≈ {gramos} g en total si fueran solidas):
  planas en la cama, relieve hacia arriba, capa 0.16 mm, 3 paredes, relleno 20 %.
  La loseta 1 es el cuarto de arriba a la derecha y siguen en contra del reloj.
Marco 1-4 (PLA de cualquier color, ≈ {gramos_marco} g): planos, relleno 20 %.
  El marco 1 lleva el ojo de cerradura para colgar y va arriba.
Aro 1-4 (PLA negro, ≈ {gramos_aro} g): de pie, con la pestana en la cama; el labio
  de arriba tiene 45 grados y no necesita soportes. El aro 3 lleva el agujero del cable.

Armado:
  1. Une las 4 piezas del marco con sus colas de milano (una gota de pegamento).
  2. Pega los 4 arcos del aro alrededor del marco: el marco asienta en la pestana de abajo.
  3. Pega la tira LED (COB blanca neutra de 8-10 mm, ≈ {tira_cm} cm, USB 5 V) por dentro
     del aro, justo debajo del labio, mirando al centro. Saca el cable por el agujero del aro 3.
  4. Pon silicon en el marco y asienta las losetas (la junta de las losetas cae sobre los rayos).
"""
