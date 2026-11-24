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
    diametro: float = Field(400, ge=200, le=600)        # hasta Ø410 en 4 piezas por parte; mas grande, en mas
    alto_relieve: float = Field(5, ge=2, le=8)          # cuanto sobresalen los crateres


class LunaPared(Linea):
    id = "luna_pared"
    nombre = "Lunas de pared"
    Config = ConfigLunaPared
    productos = [
        {"id": "luna-pared-40", "nombre": "Luna de pared Ø40 cm", "precio": 2499, "config": {"diametro": 400}},
        {"id": "luna-pared-60", "nombre": "Luna de pared Ø60 cm", "precio": 4999, "config": {"diametro": 600}},
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
                color = colores[stl.stem.rstrip("0123456789")]  # loseta01 -> loseta
                z.write(stl, f"pedido{pedido.id}_{stl.stem}_{color}.stl")
                stl.unlink()
            z.writestr("LEEME.txt", LEEME.format(**r, material=c.material.value.upper()))
        piezas.rmdir()
        return r


LEEME = """Luna de pared ({medidas})

Losetas 01-{losetas:02d} ({material} blanco, ≈ {gramos} g en total si fueran solidas):
  planas en la cama, relieve hacia arriba, capa 0.16 mm, 3 paredes, relleno 20 %.
  Las losetas 01-04 son los cuartos del centro: 01 arriba a la derecha y siguen en contra del
  reloj. Si hay mas, son el anillo de afuera, empezando a la derecha y en contra del reloj.
Marco 01-{piezas_marco:02d} (PLA de cualquier color, ≈ {gramos_marco} g): planas, relleno 20 %.
  La pieza 01 lleva el ojo de cerradura para colgar y va arriba.
Aro 01-{piezas_aro:02d} (PLA negro, ≈ {gramos_aro} g): de pie, con la pestana en la cama; el labio
  de arriba tiene 45 grados y no necesita soportes. El arco de abajo lleva el agujero del cable.

Armado:
  1. Une las piezas del marco con sus colas de milano (una gota de pegamento en cada una).
  2. Pega los arcos del aro alrededor del marco: el marco asienta en la pestana de abajo.
  3. Pega la tira LED (COB blanca neutra de 8-10 mm, ≈ {tira_cm} cm, USB 5 V) por dentro
     del aro, justo debajo del labio, mirando al centro. Saca el cable por el agujero de abajo.
  4. Pon silicon en el marco y asienta las losetas: sus juntas caen sobre los rayos y aros.
"""
