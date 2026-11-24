"""Linea de producto: cubo de 4 fotos (4 caras litofano con base de luz y tapa)."""
import zipfile
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from ...nucleo.modelos import Fase, Pedido
from ..base import Archivo, Linea, Paso
from . import generador


class Material(str, Enum):
    pla = "pla"
    petg = "petg"


class Encuadre(BaseModel):
    x: float = Field(0.5, ge=0, le=1)
    y: float = Field(0.5, ge=0, le=1)
    zoom: float = Field(1.0, ge=1, le=4)


class ConfigCubo(BaseModel):
    material: Material = Material.pla
    lado: float = Field(80, ge=50, le=150)
    mejorar: bool = True  # contraste local (CLAHE)
    # encuadre de cada foto, en el orden de las caras (1 al frente, luego hacia la derecha)
    encuadres: list[Encuadre] = Field(default_factory=lambda: [Encuadre() for _ in range(4)],
                                      min_length=4, max_length=4)


class Cubo(Linea):
    id = "cubo"
    nombre = "Cubos de 4 fotos"
    Config = ConfigCubo
    productos = [
        {"id": "cubo-80", "nombre": "Cubo de 4 fotos 80 mm", "precio": 999, "config": {"lado": 80}},
    ]
    flujo = [
        Paso("nuevo", "Nuevo", Fase.nuevo),
        Paso("previa_enviada", "Vista previa enviada", Fase.diseno),
        Paso("aprobado", "Aprobado", Fase.aprobado),
        Paso("imprimiendo", "Imprimiendo", Fase.produccion),
        Paso("listo", "Listo para entregar", Fase.listo),
        Paso("entregado", "Entregado", Fase.entregado),
        Paso("cancelado", "Cancelado", Fase.cancelado),
    ]
    archivo = Archivo("4 fotos del cliente", "image/*", cantidad=4)
    descarga = "cubo.zip"

    def acepta_archivo(self, nombre: str, tipo: str) -> bool:
        return tipo.startswith("image/")

    def generar(self, pedido: Pedido, carpeta: Path) -> dict:
        c = ConfigCubo(**pedido.config)
        fotos = [str(carpeta / n) for n in pedido.archivos]
        piezas = carpeta / "piezas"
        r = generador.generar(fotos, piezas, c.lado, c.material.value,
                              encuadres=[(e.x, e.y, e.zoom) for e in c.encuadres], mejorar=c.mejorar,
                              previa=str(carpeta / "previa.png"))
        with zipfile.ZipFile(carpeta / self.descarga, "w", zipfile.ZIP_DEFLATED) as z:
            for stl in sorted(piezas.glob("*.stl")):
                color = "blanco" if stl.stem.startswith("cara") else "color"
                z.write(stl, f"pedido{pedido.id}_{stl.stem}_{color}.stl")
                stl.unlink()
            z.writestr("LEEME.txt", LEEME.format(**r, material=c.material.value.upper()))
        piezas.rmdir()
        return r


LEEME = """Cubo de 4 fotos ({medidas})

Caras 1-4 ({material} blanco, ≈ {gramos} g en total):
  de pie, con la cara plana hacia el frente, capa 0.12 mm, relleno 100 %, brim 5 mm.
  La cara 1 va al frente y las demas siguen hacia la derecha.
Base y tapa (PLA de color, ≈ {gramos_base_tapa} g):
  base con la ranura hacia arriba; tapa volteada (ranura hacia arriba en la cama).
Armado: pega la tira LED al piso de la base, saca el cable por la ranura trasera,
mete las 4 caras en la ranura (los cantos a 45 grados se juntan en las esquinas)
y pon la tapa. Una gota de pegamento en cada esquina si quedan flojas.
"""
