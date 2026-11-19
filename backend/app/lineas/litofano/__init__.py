"""Linea de producto: lamparas con litofano a partir de la foto del cliente."""
import io
import zipfile
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from ...nucleo.db import ARCHIVOS, sesion
from ...nucleo.modelos import Fase, Pedido
from ..base import Archivo, Linea, Paso
from . import generador


class Forma(str, Enum):
    panel = "panel"
    cilindro = "cilindro"


class Material(str, Enum):
    pla = "pla"
    petg = "petg"


class ConfigLitofano(BaseModel):
    forma: Forma = Forma.panel
    material: Material = Material.petg
    ancho: float = Field(150, gt=0)
    diametro: float = Field(80, gt=0)
    alto: float = Field(100, gt=0)
    # encuadre de la foto: centro del recorte (0-1) y acercamiento (1 = toda la foto)
    encuadre_x: float = Field(0.5, ge=0, le=1)
    encuadre_y: float = Field(0.5, ge=0, le=1)
    zoom: float = Field(1.0, ge=1, le=4)
    mejorar: bool = True  # contraste local (CLAHE)


def _parametros(c: ConfigLitofano) -> dict:
    return {"forma": c.forma.value, "material": c.material.value, "ancho": c.ancho, "diametro": c.diametro,
            "alto": c.alto}


router = APIRouter(prefix="/api/lineas/litofano")


@router.get("/pedidos/{pedido_id}/ensayo")
async def ensayo(pedido_id: int, x: float = Query(0.5, ge=0, le=1), y: float = Query(0.5, ge=0, le=1),
                 zoom: float = Query(1.0, ge=1, le=4), mejorar: bool = True, s: Session = Depends(sesion)):
    """Vista previa rapida (baja resolucion, sin STL) para probar el encuadre antes de guardarlo."""
    p = s.get(Pedido, pedido_id)
    if not p or p.linea != Litofano.id:
        raise HTTPException(404, "Pedido no encontrado")
    c = ConfigLitofano(**p.config)
    esp = await run_in_threadpool(generador.espesores, str(ARCHIVOS / p.carpeta / p.archivo), **_parametros(c),
                                  resolucion=0.5, encuadre=(x, y, zoom), mejorar=mejorar)
    buf = io.BytesIO()
    generador.vista_previa(esp, buf, k=generador.MATERIALES[c.material.value]["k"])
    return Response(buf.getvalue(), media_type="image/png")


class Litofano(Linea):
    id = "litofano"
    nombre = "Litofanos"
    Config = ConfigLitofano
    # Catalogo inicial (precios en MXN del plan); editable aqui.
    productos = [
        {"id": "panel-150", "nombre": "Panel clásico 150 mm", "precio": 449,
         "config": {"forma": "panel", "ancho": 150}},
        {"id": "panel-100", "nombre": "Panel chico 100 mm", "precio": 399,
         "config": {"forma": "panel", "ancho": 100}},
        {"id": "cilindro-80", "nombre": "Lámpara cilindro Ø80 × 100 mm", "precio": 649,
         "config": {"forma": "cilindro", "diametro": 80, "alto": 100}},
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
    archivo = Archivo("Foto del cliente", "image/*")
    descarga = "litofano.zip"
    router = router

    def acepta_archivo(self, nombre: str, tipo: str) -> bool:
        return tipo.startswith("image/")

    def generar(self, pedido: Pedido, carpeta: Path) -> dict:
        c = ConfigLitofano(**pedido.config)
        stl = carpeta / "litofano.stl"
        r = generador.generar(str(carpeta / pedido.archivo), str(stl), **_parametros(c),
                              previa=str(carpeta / "previa.png"), encuadre=(c.encuadre_x, c.encuadre_y, c.zoom),
                              mejorar=c.mejorar)
        with zipfile.ZipFile(carpeta / self.descarga, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(stl, f"pedido{pedido.id}_{c.forma.value}_{c.material.value}.stl")
        stl.unlink()
        return {"gramos": r["gramos"], "medidas": r["medidas"]}
