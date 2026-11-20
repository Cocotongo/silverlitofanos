"""Linea de producto: letreros LED tipo neon a partir de un texto."""
from dataclasses import fields
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field as PField
from sqlalchemy import inspect, text
from sqlmodel import Field, Session, SQLModel, select

from ...nucleo.db import engine, sesion
from ...nucleo.modelos import Fase, Pedido
from ..base import Linea, Paso
from . import generador
from .generador import Perfil


class PerfilLed(SQLModel, table=True):
    """Medidas de construccion editables (cambian si cambia el proveedor de la tira)."""
    __tablename__ = "perfil_led"
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str
    proveedor: str = ""
    ancho_tira: float = Field(default=10.0, gt=0)
    holgura_tira: float = Field(default=1.0, ge=0)
    alto_tunel: float = Field(default=13.0, gt=0)
    profundidad: float = Field(default=50.0, gt=0)
    base: float = Field(default=1.0, gt=0)
    fondo_canal: float = Field(default=30.0, gt=0)
    pared: float = Field(default=9.2, gt=0)
    escalon: float = Field(default=1.2, ge=0)
    tapa_pared: float = Field(default=0.9, gt=0)
    tapa_frente: float = Field(default=0.4, gt=0)
    tapa_holgura: float = Field(default=0.3, ge=0)
    holgura_union: float = Field(default=0.2, ge=0)
    pieza_max: float = Field(default=210.0, gt=20)
    colgador_diam: float = Field(default=9.0, gt=0)
    colgador_largo: float = Field(default=15.0, gt=0)
    cable_ancho: float = Field(default=10.0, gt=0)
    cable_largo: float = Field(default=8.0, gt=0)
    cola_largo: float = Field(default=5.0, ge=0)
    cola_cuello: float = Field(default=4.0, gt=0)
    cola_cabeza: float = Field(default=6.0, gt=0)
    cola_holgura: float = Field(default=0.2, ge=0)
    cola_alto: float = Field(default=25.0, gt=0)

    def medidas(self) -> Perfil:
        return Perfil(**{f.name: getattr(self, f.name) for f in fields(Perfil)})


class PerfilLedDatos(SQLModel):
    """Lo que se puede mandar al crear o editar un perfil (todo opcional al editar)."""
    nombre: Optional[str] = None
    proveedor: Optional[str] = None
    ancho_tira: Optional[float] = PField(default=None, gt=0)
    holgura_tira: Optional[float] = PField(default=None, ge=0)
    alto_tunel: Optional[float] = PField(default=None, gt=0)
    profundidad: Optional[float] = PField(default=None, gt=0)
    base: Optional[float] = PField(default=None, gt=0)
    fondo_canal: Optional[float] = PField(default=None, gt=0)
    pared: Optional[float] = PField(default=None, gt=0)
    escalon: Optional[float] = PField(default=None, ge=0)
    tapa_pared: Optional[float] = PField(default=None, gt=0)
    tapa_frente: Optional[float] = PField(default=None, gt=0)
    tapa_holgura: Optional[float] = PField(default=None, ge=0)
    holgura_union: Optional[float] = PField(default=None, ge=0)
    pieza_max: Optional[float] = PField(default=None, gt=20)
    colgador_diam: Optional[float] = PField(default=None, gt=0)
    colgador_largo: Optional[float] = PField(default=None, gt=0)
    cable_ancho: Optional[float] = PField(default=None, gt=0)
    cable_largo: Optional[float] = PField(default=None, gt=0)
    cola_largo: Optional[float] = PField(default=None, ge=0)
    cola_cuello: Optional[float] = PField(default=None, gt=0)
    cola_cabeza: Optional[float] = PField(default=None, gt=0)
    cola_holgura: Optional[float] = PField(default=None, ge=0)
    cola_alto: Optional[float] = PField(default=None, gt=0)


class ConfigLetrero(BaseModel):
    texto: str = PField("SilVer", min_length=1, max_length=80)
    fuente: str = "Pacifico-Regular"
    altura: float = PField(120, gt=10, le=400)  # alto de las mayusculas, mm
    perfil_id: Optional[int] = None  # None = el primer perfil


def perfil_de(s: Session, perfil_id: Optional[int]) -> PerfilLed:
    p = s.get(PerfilLed, perfil_id) if perfil_id else s.exec(select(PerfilLed).order_by(PerfilLed.id)).first()
    if not p:
        p = PerfilLed(nombre="Tira 10 mm (base)")
        s.add(p)
        s.commit()
        s.refresh(p)
    return p


router = APIRouter(prefix="/api/lineas/letrero")


@router.get("/fuentes")
def lista_fuentes():
    return generador.fuentes()


@router.get("/perfiles", response_model=list[PerfilLed])
def perfiles(s: Session = Depends(sesion)):
    perfil_de(s, None)  # garantiza que exista al menos uno
    return s.exec(select(PerfilLed).order_by(PerfilLed.id)).all()


@router.post("/perfiles", response_model=PerfilLed, status_code=201)
def crear_perfil(datos: PerfilLedDatos, s: Session = Depends(sesion)):
    valores = datos.model_dump(exclude_none=True)
    if not valores.get("nombre"):
        raise HTTPException(422, "El perfil necesita nombre")
    p = PerfilLed(**valores)
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@router.patch("/perfiles/{perfil_id}", response_model=PerfilLed)
def editar_perfil(perfil_id: int, datos: PerfilLedDatos, s: Session = Depends(sesion)):
    p = s.get(PerfilLed, perfil_id)
    if not p:
        raise HTTPException(404, "Perfil no encontrado")
    for k, v in datos.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@router.delete("/perfiles/{perfil_id}", status_code=204)
def borrar_perfil(perfil_id: int, s: Session = Depends(sesion)):
    p = s.get(PerfilLed, perfil_id)
    if not p:
        raise HTTPException(404, "Perfil no encontrado")
    if len(s.exec(select(PerfilLed)).all()) == 1:
        raise HTTPException(409, "Debe quedar al menos un perfil")
    s.delete(p)
    s.commit()


@router.get("/ensayo")
async def ensayo(texto: str = Query(..., min_length=1, max_length=80), fuente: str = "Pacifico-Regular",
                 altura: float = Query(120, gt=10, le=400), perfil_id: Optional[int] = None,
                 s: Session = Depends(sesion)):
    """Vista previa rapida (solo 2D): sirve para probar texto, fuente y tamano antes de crear el pedido."""
    medidas = perfil_de(s, perfil_id).medidas()
    try:
        png = await run_in_threadpool(generador.ensayo_png, texto, fuente, altura, medidas)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return Response(png, media_type="image/png")


class Letrero(Linea):
    id = "letrero"
    nombre = "Letreros LED"
    Config = ConfigLetrero
    productos = [
        {"id": "letrero-chico", "nombre": "Letrero LED chico (hasta 60 cm)", "precio": 1200,
         "config": {"altura": 90}},
        {"id": "letrero-mediano", "nombre": "Letrero LED mediano (hasta 1 m)", "precio": 1900,
         "config": {"altura": 120}},
    ]
    flujo = [
        Paso("nuevo", "Nuevo", Fase.nuevo),
        Paso("diseno_enviado", "Diseño enviado", Fase.diseno),
        Paso("aprobado", "Aprobado", Fase.aprobado),
        Paso("imprimiendo", "Imprimiendo", Fase.produccion),
        Paso("armando", "Armando y cableando", Fase.produccion),
        Paso("listo", "Listo para entregar", Fase.listo),
        Paso("entregado", "Entregado", Fase.entregado),
        Paso("cancelado", "Cancelado", Fase.cancelado),
    ]
    archivo = None
    descarga = "letrero.zip"
    router = router

    def config_inicial(self, producto, extra):
        c = super().config_inicial(producto, extra)
        if c["fuente"] not in generador.fuentes():
            raise HTTPException(422, f"Fuente desconocida: {c['fuente']}")
        return c

    def actualizar_config(self, actual, cambios):
        c = super().actualizar_config(actual, cambios)
        if c["fuente"] not in generador.fuentes():
            raise HTTPException(422, f"Fuente desconocida: {c['fuente']}")
        return c

    def migrar(self, engine):
        """Agrega a perfil_led las medidas nuevas (con su valor por defecto) si la tabla es de antes."""
        with engine.begin() as con:
            existentes = {c["name"] for c in inspect(con).get_columns("perfil_led")}
            for campo, info in PerfilLed.model_fields.items():
                if campo not in existentes and isinstance(info.default, float):
                    con.execute(text(f"ALTER TABLE perfil_led ADD COLUMN {campo} FLOAT DEFAULT {info.default}"))

    def generar(self, pedido: Pedido, carpeta: Path) -> dict:
        c = ConfigLetrero(**pedido.config)
        with Session(engine) as s:
            perfil = perfil_de(s, c.perfil_id)
            nombre = perfil.nombre
            medidas = perfil.medidas()
        try:
            r = generador.generar(c.texto, c.fuente, c.altura, medidas, carpeta)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {**r, "perfil_nombre": nombre}

