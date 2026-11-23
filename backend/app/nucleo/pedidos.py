"""Rutas de pedidos comunes a todas las lineas de producto."""
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlmodel import Session, select

from ..lineas import LINEAS, linea
from .db import ARCHIVOS, sesion
from .modelos import Pedido, PedidoCambios

router = APIRouter(prefix="/api")


def carpeta(p: Pedido) -> Path:
    return ARCHIVOS / p.carpeta


def obtener(s: Session, pedido_id: int) -> Pedido:
    p = s.get(Pedido, pedido_id)
    if not p:
        raise HTTPException(404, "Pedido no encontrado")
    return p


def validar(fn, *args):
    try:
        return fn(*args)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False))


@router.get("/lineas")
def lineas():
    return [l.describir() for l in LINEAS.values()]


@router.get("/productos")
def productos():
    return [{**p, "linea": l.id} for l in LINEAS.values() for p in l.productos]


@router.get("/pedidos", response_model=list[Pedido])
def listar(estado: Optional[str] = None, linea: Optional[str] = None, s: Session = Depends(sesion)):
    q = select(Pedido).order_by(Pedido.creado.desc())
    if estado:
        q = q.where(Pedido.estado == estado)
    if linea:
        q = q.where(Pedido.linea == linea)
    return s.exec(q).all()


@router.post("/pedidos", response_model=Pedido, status_code=201)
async def crear(cliente: str = Form(...), telefono: str = Form(""), canal: str = Form("WhatsApp"),
                linea_id: str = Form("litofano", alias="linea"), producto: str = Form(...),
                config: str = Form("{}"), precio: Optional[float] = Form(None), anticipo: float = Form(0),
                notas: str = Form(""), fecha_entrega: Optional[date] = Form(None),
                archivo: Optional[UploadFile] = File(None), archivos: Optional[list[UploadFile]] = File(None),
                s: Session = Depends(sesion)):
    l = linea(linea_id)
    prod = l.producto(producto)
    if not prod:
        raise HTTPException(400, "Producto desconocido")
    try:
        extra = json.loads(config)
    except ValueError:
        raise HTTPException(400, "config debe ser JSON")
    subidos = ([archivo] if archivo else []) + list(archivos or [])
    cantidad = l.archivo.cantidad if l.archivo else 0
    if l.archivo and l.archivo.requerido and len(subidos) < cantidad:
        faltan = cantidad - len(subidos)
        raise HTTPException(400, f"Falta el archivo: {l.archivo.etiqueta}" if cantidad == 1
                            else f"Faltan {faltan} de {cantidad} archivos: {l.archivo.etiqueta}")
    if len(subidos) > max(cantidad, 1):
        raise HTTPException(400, f"{l.nombre} lleva {cantidad} archivo(s), llegaron {len(subidos)}")
    for a in subidos:
        if not l.acepta_archivo(a.filename or "", a.content_type or ""):
            raise HTTPException(400, f"Archivo no válido para {l.nombre}")
    p = Pedido(cliente=cliente, telefono=telefono, canal=canal, linea=l.id, producto=producto,
               precio=prod["precio"] if precio is None else precio, anticipo=anticipo, notas=notas,
               fecha_entrega=fecha_entrega, estado=l.flujo[0].id, config=validar(l.config_inicial, prod, extra))
    destino = carpeta(p)
    destino.mkdir(parents=True)
    for i, a in enumerate(subidos, 1):
        nombre = f"original{'' if len(subidos) == 1 else f'_{i}'}{Path(a.filename or '').suffix.lower()}"
        with open(destino / nombre, "wb") as f:
            shutil.copyfileobj(a.file, f)
        p.archivos = [*p.archivos, nombre]
    p.archivo = p.archivos[0] if p.archivos else ""
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@router.get("/pedidos/{pedido_id}", response_model=Pedido)
def ver(pedido_id: int, s: Session = Depends(sesion)):
    return obtener(s, pedido_id)


@router.patch("/pedidos/{pedido_id}", response_model=Pedido)
def actualizar(pedido_id: int, cambios: PedidoCambios, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    l = linea(p.linea)
    datos = cambios.model_dump(exclude_unset=True)
    if "estado" in datos and not l.paso(datos["estado"]):
        raise HTTPException(422, f"Estado no válido para {l.nombre}")
    if datos.get("config") is not None:
        nueva = validar(l.actualizar_config, p.config, datos["config"])
        if nueva != p.config:
            p.config, p.generado, p.resumen = nueva, False, {}  # cambiaron los datos: hay que regenerar
    for k, v in datos.items():
        if k != "config":
            setattr(p, k, v)
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@router.delete("/pedidos/{pedido_id}", status_code=204)
def borrar(pedido_id: int, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    shutil.rmtree(carpeta(p), ignore_errors=True)
    s.delete(p)
    s.commit()


@router.post("/pedidos/{pedido_id}/generar", response_model=Pedido)
async def generar(pedido_id: int, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    p.resumen = await run_in_threadpool(linea(p.linea).generar, p, carpeta(p))
    p.generado = True
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


def servir(p: Pedido, nombre: str, descarga: Optional[str] = None):
    ruta = carpeta(p) / nombre
    if not nombre or not ruta.is_file():
        raise HTTPException(404, "Archivo no disponible")
    return FileResponse(ruta, filename=descarga)


@router.get("/pedidos/{pedido_id}/archivo")
def archivo_original(pedido_id: int, n: int = Query(1, ge=1), s: Session = Depends(sesion)):
    """Archivo del cliente; n = 1, 2... cuando el pedido lleva varios."""
    p = obtener(s, pedido_id)
    nombres = p.archivos or [p.archivo]
    return servir(p, nombres[n - 1] if n <= len(nombres) else "")


@router.get("/pedidos/{pedido_id}/previa")
def previa(pedido_id: int, s: Session = Depends(sesion)):
    return servir(obtener(s, pedido_id), "previa.png")


@router.get("/pedidos/{pedido_id}/descarga")
def descarga(pedido_id: int, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    l = linea(p.linea)
    if not p.generado:
        raise HTTPException(404, "Archivo no disponible")
    return servir(p, l.descarga, l.nombre_descarga(p))
