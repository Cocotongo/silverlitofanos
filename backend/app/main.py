"""API de SilVer: pedidos de varias lineas de producto (litofanos, y despues letreros LED, juguetes...).

Ejecutar:  uvicorn app.main:app --reload   (desde la carpeta backend)

- app/nucleo/: lo comun a cualquier venta (pedidos, cobros, fechas, archivos del pedido).
- app/lineas/: un modulo por linea de producto (que datos pide, que genera, sus pasos).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .lineas import LINEAS
from .nucleo import pedidos
from .nucleo.db import engine
from .nucleo.migracion import iniciar

iniciar(engine)
for _l in LINEAS.values():
    _l.migrar(engine)

app = FastAPI(title="SilVer")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"], allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(pedidos.router)
for l in LINEAS.values():
    if l.router:
        app.include_router(l.router)
