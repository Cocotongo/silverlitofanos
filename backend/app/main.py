"""API de pedidos de SilVerLitofanos.

Ejecutar:  uvicorn app.main:app --reload   (desde la carpeta backend)
"""
import io
import os
import shutil
import uuid
import zipfile
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import inspect, text
from sqlmodel import Field, Session, SQLModel, create_engine, select

from . import litofano

DATOS = Path(os.environ.get("SILVER_DATOS", Path(__file__).resolve().parent.parent / "datos"))
ARCHIVOS = DATOS / "pedidos"
ARCHIVOS.mkdir(parents=True, exist_ok=True)


class Estado(str, Enum):
    nuevo = "nuevo"
    previa_enviada = "previa_enviada"
    aprobado = "aprobado"
    imprimiendo = "imprimiendo"
    listo = "listo"
    entregado = "entregado"
    cancelado = "cancelado"


class Forma(str, Enum):
    panel = "panel"
    cilindro = "cilindro"


class Material(str, Enum):
    pla = "pla"
    petg = "petg"


# Catalogo inicial (precios en MXN del plan); editable aqui.
PRODUCTOS = [
    {"id": "panel-150", "nombre": "Panel clásico 150 mm", "forma": "panel", "ancho": 150, "precio": 449},
    {"id": "panel-100", "nombre": "Panel chico 100 mm", "forma": "panel", "ancho": 100, "precio": 399},
    {"id": "cilindro-80", "nombre": "Lámpara cilindro Ø80 × 100 mm", "forma": "cilindro",
     "diametro": 80, "alto": 100, "precio": 649},
]


class Pedido(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    cliente: str
    telefono: str = ""
    canal: str = "WhatsApp"
    producto: str = "panel-150"
    forma: Forma = Forma.panel
    material: Material = Material.petg
    ancho: float = 150
    diametro: float = 80
    alto: float = 100
    # encuadre de la foto: centro del recorte (0-1) y acercamiento (1 = toda la foto)
    encuadre_x: float = Field(default=0.5, ge=0, le=1)
    encuadre_y: float = Field(default=0.5, ge=0, le=1)
    zoom: float = Field(default=1.0, ge=1, le=4)
    mejorar: bool = True  # contraste local (CLAHE)
    precio: float = 0
    anticipo: float = 0
    estado: Estado = Estado.nuevo
    notas: str = ""
    fecha_entrega: Optional[date] = None
    creado: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    carpeta: str = Field(default_factory=lambda: uuid.uuid4().hex)
    foto_nombre: str = ""
    stl_listo: bool = False
    gramos: Optional[float] = None
    medidas: str = ""


class PedidoCambios(SQLModel):
    cliente: Optional[str] = None
    telefono: Optional[str] = None
    canal: Optional[str] = None
    forma: Optional[Forma] = None
    material: Optional[Material] = None
    ancho: Optional[float] = None
    diametro: Optional[float] = None
    alto: Optional[float] = None
    encuadre_x: Optional[float] = Field(default=None, ge=0, le=1)
    encuadre_y: Optional[float] = Field(default=None, ge=0, le=1)
    zoom: Optional[float] = Field(default=None, ge=1, le=4)
    mejorar: Optional[bool] = None
    precio: Optional[float] = None
    anticipo: Optional[float] = None
    estado: Optional[Estado] = None
    notas: Optional[str] = None
    fecha_entrega: Optional[date] = None


engine = create_engine(f"sqlite:///{DATOS / 'pedidos.db'}", connect_args={"check_same_thread": False})


def sesion():
    with Session(engine) as s:
        yield s


app = FastAPI(title="SilVerLitofanos")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"], allow_methods=["*"],
                   allow_headers=["*"])


SQLModel.metadata.create_all(engine)

# columnas agregadas despues de la primera version: se suman a bases de datos existentes
NUEVAS_COLUMNAS = {"encuadre_x": "FLOAT DEFAULT 0.5", "encuadre_y": "FLOAT DEFAULT 0.5",
                   "zoom": "FLOAT DEFAULT 1.0", "mejorar": "BOOLEAN DEFAULT 1"}
with engine.begin() as con:
    existentes = {c["name"] for c in inspect(con).get_columns("pedido")}
    for nombre, tipo in NUEVAS_COLUMNAS.items():
        if nombre not in existentes:
            con.execute(text(f"ALTER TABLE pedido ADD COLUMN {nombre} {tipo}"))


def carpeta(p: Pedido) -> Path:
    return ARCHIVOS / p.carpeta


def obtener(s: Session, pedido_id: int) -> Pedido:
    p = s.get(Pedido, pedido_id)
    if not p:
        raise HTTPException(404, "Pedido no encontrado")
    return p


@app.get("/api/productos")
def productos():
    return PRODUCTOS


@app.get("/api/pedidos", response_model=list[Pedido])
def listar(estado: Optional[Estado] = None, s: Session = Depends(sesion)):
    q = select(Pedido).order_by(Pedido.creado.desc())
    if estado:
        q = q.where(Pedido.estado == estado)
    return s.exec(q).all()


@app.post("/api/pedidos", response_model=Pedido, status_code=201)
async def crear(cliente: str = Form(...), telefono: str = Form(""), canal: str = Form("WhatsApp"),
                producto: str = Form("panel-150"), material: Material = Form(Material.petg),
                precio: Optional[float] = Form(None), anticipo: float = Form(0), notas: str = Form(""),
                fecha_entrega: Optional[date] = Form(None), foto: UploadFile = File(...),
                s: Session = Depends(sesion)):
    prod = next((x for x in PRODUCTOS if x["id"] == producto), None)
    if not prod:
        raise HTTPException(400, "Producto desconocido")
    if not (foto.content_type or "").startswith("image/"):
        raise HTTPException(400, "La foto debe ser una imagen")
    p = Pedido(cliente=cliente, telefono=telefono, canal=canal, producto=producto, forma=prod["forma"],
               material=material, ancho=prod.get("ancho", 150), diametro=prod.get("diametro", 80),
               alto=prod.get("alto", 100), precio=prod["precio"] if precio is None else precio,
               anticipo=anticipo, notas=notas, fecha_entrega=fecha_entrega)
    destino = carpeta(p)
    destino.mkdir(parents=True)
    ext = Path(foto.filename or "foto.jpg").suffix.lower() or ".jpg"
    p.foto_nombre = f"foto{ext}"
    with open(destino / p.foto_nombre, "wb") as f:
        shutil.copyfileobj(foto.file, f)
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@app.get("/api/pedidos/{pedido_id}", response_model=Pedido)
def ver(pedido_id: int, s: Session = Depends(sesion)):
    return obtener(s, pedido_id)


AJUSTES_FOTO = {"encuadre_x", "encuadre_y", "zoom", "mejorar"}


@app.patch("/api/pedidos/{pedido_id}", response_model=Pedido)
def actualizar(pedido_id: int, cambios: PedidoCambios, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    datos = cambios.model_dump(exclude_unset=True)
    for k, v in datos.items():
        setattr(p, k, v)
    if {"forma", "material", "ancho", "diametro", "alto"} & datos.keys() or AJUSTES_FOTO & datos.keys():
        p.stl_listo = False  # cambio de medidas: hay que regenerar
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


@app.delete("/api/pedidos/{pedido_id}", status_code=204)
def borrar(pedido_id: int, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    shutil.rmtree(carpeta(p), ignore_errors=True)
    s.delete(p)
    s.commit()


@app.post("/api/pedidos/{pedido_id}/generar", response_model=Pedido)
async def generar(pedido_id: int, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    d = carpeta(p)
    stl = d / "litofano.stl"
    resumen = await run_in_threadpool(
        litofano.generar, str(d / p.foto_nombre), str(stl), forma=p.forma.value,
        material=p.material.value, ancho=p.ancho, diametro=p.diametro, alto=p.alto,
        previa=str(d / "previa.png"), encuadre=(p.encuadre_x, p.encuadre_y, p.zoom), mejorar=p.mejorar)
    with zipfile.ZipFile(d / "litofano.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(stl, f"pedido{p.id}_{p.forma.value}_{p.material.value}.stl")
    stl.unlink()
    p.stl_listo, p.gramos, p.medidas = True, resumen["gramos"], resumen["medidas"]
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


def archivo(p: Pedido, nombre: str, descarga: Optional[str] = None):
    ruta = carpeta(p) / nombre
    if not ruta.exists():
        raise HTTPException(404, "Archivo no disponible")
    return FileResponse(ruta, filename=descarga)


@app.get("/api/pedidos/{pedido_id}/foto")
def foto(pedido_id: int, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    return archivo(p, p.foto_nombre)


@app.get("/api/pedidos/{pedido_id}/previa")
def previa(pedido_id: int, s: Session = Depends(sesion)):
    return archivo(obtener(s, pedido_id), "previa.png")


@app.get("/api/pedidos/{pedido_id}/ensayo")
async def ensayo(pedido_id: int, x: float = Query(0.5, ge=0, le=1), y: float = Query(0.5, ge=0, le=1),
                 zoom: float = Query(1.0, ge=1, le=4), mejorar: bool = True, s: Session = Depends(sesion)):
    """Vista previa rapida (baja resolucion, sin STL) para probar el encuadre antes de guardarlo."""
    p = obtener(s, pedido_id)
    esp = await run_in_threadpool(
        litofano.espesores, str(carpeta(p) / p.foto_nombre), forma=p.forma.value,
        material=p.material.value, ancho=p.ancho, diametro=p.diametro, alto=p.alto, resolucion=0.5,
        encuadre=(x, y, zoom), mejorar=mejorar)
    buf = io.BytesIO()
    litofano.vista_previa(esp, buf, k=litofano.MATERIALES[p.material.value]["k"])
    return Response(buf.getvalue(), media_type="image/png")


@app.get("/api/pedidos/{pedido_id}/stl")
def stl(pedido_id: int, s: Session = Depends(sesion)):
    p = obtener(s, pedido_id)
    return archivo(p, "litofano.zip", f"pedido{p.id}_{p.cliente.replace(' ', '_')}.zip")
