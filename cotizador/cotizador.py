"""Cotizador SilVer: busca un producto en varias tiendas a la vez y compara precios.

Escribes una consulta ("pla blanco 1kg") y el cotizador abre la búsqueda de cada
tienda definida en tiendas.json con un Chrome propio (se abre solo, sin que lo veas),
lee los productos y precios de la página y te los regresa juntos, del más barato
al más caro.

Arrancar (desde esta carpeta):
    python cotizador.py          -> abre http://localhost:8765
    python cotizador.py --ver    -> igual, pero muestra la ventana de Chrome
                                    (sirve para resolver un "no soy robot" o iniciar sesión)
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import time
import webbrowser
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, quote_plus

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

AQUI = Path(__file__).resolve().parent
TIENDAS = AQUI / "tiendas.json"
HISTORIAL = AQUI / "datos" / "historial.csv"
PERFIL = AQUI / "datos" / "perfil-chrome"
EXTRAER_JS = (AQUI / "extraer.js").read_text(encoding="utf-8")
EXTRAER_JS = EXTRAER_JS[EXTRAER_JS.index("(cfg)"):]  # sin los comentarios de arriba

PUERTO = 8765
ESPERA_PRODUCTOS_MS = 12_000
LIMITE_TIENDA_S = 35


# ---------------------------------------------------------------- tiendas


class Tienda(BaseModel):
    nombre: str = Field(min_length=1)
    activa: bool = True
    busqueda: str = Field(min_length=8, description="URL de búsqueda con {q}, {q+} o {q-}")
    item: str = Field(min_length=1, description="Selector CSS de cada producto")
    titulo: str = Field(min_length=1)
    precio: str = ""
    precio_attr: str = ""
    enlace: str = ""
    max: int = 20


def leer_tiendas() -> list[Tienda]:
    return [Tienda(**t) for t in json.loads(TIENDAS.read_text(encoding="utf-8"))]


def guardar_tiendas(tiendas: list[Tienda]) -> None:
    datos = [t.model_dump(exclude_defaults=False) for t in tiendas]
    TIENDAS.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def url_busqueda(plantilla: str, consulta: str) -> str:
    """{q} -> "pla%20blanco", {q+} -> "pla+blanco", {q-} -> "pla-blanco"."""
    palabras = consulta.split()
    return (plantilla
            .replace("{q+}", "+".join(quote_plus(p) for p in palabras))
            .replace("{q-}", "-".join(quote(p.lower()) for p in palabras))
            .replace("{q}", quote(" ".join(palabras))))


# ---------------------------------------------------------------- navegador


class Navegador:
    """Un Chrome con perfil propio (datos/perfil-chrome): guarda cookies, así que si una
    tienda pide "no soy robot" o país, lo resuelves una vez con --ver y queda."""

    def __init__(self, visible: bool):
        self.visible = visible
        self._pw = None
        self._ctx = None
        self.motor = ""
        self._lock = asyncio.Lock()

    async def abrir(self):
        from playwright.async_api import async_playwright

        PERFIL.mkdir(parents=True, exist_ok=True)
        self._pw = await async_playwright().start()
        opciones = dict(
            user_data_dir=str(PERFIL),
            headless=not self.visible,
            locale="es-MX",
            timezone_id="America/Monterrey",
            viewport={"width": 1366, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        if os.environ.get("COTIZADOR_CHROME"):  # ruta a un Chrome/Chromium en particular
            opciones["executable_path"] = os.environ["COTIZADOR_CHROME"]
        try:  # el Chrome que ya tienes instalado
            if "executable_path" in opciones:
                raise RuntimeError
            self._ctx = await self._pw.chromium.launch_persistent_context(channel="chrome", **opciones)
            self.motor = "Google Chrome"
        except Exception:  # el Chromium de Playwright (python -m playwright install chromium)
            self._ctx = await self._pw.chromium.launch_persistent_context(**opciones)
            self.motor = "Chromium"
        # Sin ventana, Chrome se presenta como "HeadlessChrome" y algunas tiendas lo bloquean.
        pagina = self._ctx.pages[0] if self._ctx.pages else await self._ctx.new_page()
        ua = await pagina.evaluate("navigator.userAgent")
        if "Headless" in ua:
            ua = ua.replace("HeadlessChrome", "Chrome")
            await self._ctx.set_extra_http_headers({"User-Agent": ua})
            await self._ctx.add_init_script(
                "Object.defineProperty(navigator, 'userAgent', {get: () => %s});" % json.dumps(ua))
        await self._ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

    async def cerrar(self):
        if self._ctx:
            await self._ctx.close()
        if self._pw:
            await self._pw.stop()

    async def buscar_en(self, tienda: Tienda, consulta: str) -> dict:
        url = url_busqueda(tienda.busqueda, consulta)
        inicio = time.monotonic()
        res = {"tienda": tienda.nombre, "url": url, "estado": "ok", "mensaje": "", "resultados": []}
        pagina = await self._ctx.new_page()
        try:
            await pagina.goto(url, wait_until="domcontentloaded", timeout=25_000)
            try:
                await pagina.wait_for_selector(tienda.item, timeout=ESPERA_PRODUCTOS_MS)
            except Exception:
                pass
            # Bajar un poco: varias tiendas cargan precios e imágenes al hacer scroll.
            for _ in range(3):
                await pagina.mouse.wheel(0, 1400)
                await pagina.wait_for_timeout(450)
            datos = await pagina.evaluate(EXTRAER_JS, tienda.model_dump())
            if isinstance(datos, dict) and datos.get("error"):
                res.update(estado="error", mensaje=datos["error"])
            else:
                res["resultados"] = datos
                if not datos:
                    titulo = (await pagina.title()) or ""
                    res.update(estado="vacio", mensaje=(
                        "No encontré productos. Puede que no haya resultados, que la tienda "
                        "pida verificación (arranca con --ver y resuélvela una vez) o que "
                        f"cambió su página. Título de la página: «{titulo[:80]}»"))
        except Exception as e:  # tienda caída, sin internet, etc.
            res.update(estado="error", mensaje=str(e).splitlines()[0][:200])
        finally:
            await pagina.close()
        res["segundos"] = round(time.monotonic() - inicio, 1)
        return res

    async def buscar(self, tiendas: list[Tienda], consulta: str) -> list[dict]:
        async with self._lock:
            async def una(t: Tienda):
                try:
                    return await asyncio.wait_for(self.buscar_en(t, consulta), LIMITE_TIENDA_S)
                except asyncio.TimeoutError:
                    return {"tienda": t.nombre, "url": url_busqueda(t.busqueda, consulta),
                            "estado": "error", "mensaje": "La tienda tardó demasiado.",
                            "resultados": [], "segundos": LIMITE_TIENDA_S}
            return list(await asyncio.gather(*(una(t) for t in tiendas)))


# ---------------------------------------------------------------- historial


def guardar_historial(consulta: str, por_tienda: list[dict]) -> None:
    HISTORIAL.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not HISTORIAL.exists()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    with HISTORIAL.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fecha", "consulta", "tienda", "producto", "precio_mxn", "enlace"])
        for t in por_tienda:
            for r in t["resultados"]:
                w.writerow([fecha, consulta, t["tienda"], r["titulo"], r["precio"], r.get("url") or ""])


# ---------------------------------------------------------------- API

navegador: Navegador | None = None


@asynccontextmanager
async def ciclo(app: FastAPI):
    await navegador.abrir()
    yield
    await navegador.cerrar()


app = FastAPI(title="Cotizador SilVer", lifespan=ciclo)


class Busqueda(BaseModel):
    q: str = Field(min_length=2, max_length=120)
    tiendas: list[str] | None = None  # nombres; vacío = las activas


class Prueba(BaseModel):
    q: str = Field(min_length=2, max_length=120)
    tienda: Tienda


@app.get("/", response_class=HTMLResponse)
def inicio():
    return (AQUI / "index.html").read_text(encoding="utf-8")


@app.get("/api/estado")
def estado():
    return {"motor": navegador.motor, "visible": navegador.visible}


@app.get("/api/tiendas")
def tiendas_get():
    return leer_tiendas()


@app.put("/api/tiendas")
def tiendas_put(tiendas: list[Tienda]):
    nombres = [t.nombre.strip().lower() for t in tiendas]
    if len(set(nombres)) != len(nombres):
        raise HTTPException(400, "Hay dos tiendas con el mismo nombre.")
    if any("{q" not in t.busqueda for t in tiendas):
        raise HTTPException(400, "Cada URL de búsqueda necesita {q}, {q+} o {q-} donde va lo que buscas.")
    guardar_tiendas(tiendas)
    return leer_tiendas()


@app.post("/api/buscar")
async def buscar(b: Busqueda):
    todas = leer_tiendas()
    if b.tiendas:
        elegidas = [t for t in todas if t.nombre in b.tiendas]
    else:
        elegidas = [t for t in todas if t.activa]
    if not elegidas:
        raise HTTPException(400, "Elige al menos una tienda.")
    consulta = " ".join(b.q.split())
    por_tienda = await navegador.buscar(elegidas, consulta)
    guardar_historial(consulta, por_tienda)
    return {"q": consulta, "fecha": datetime.now().isoformat(timespec="minutes"), "tiendas": por_tienda}


@app.post("/api/probar")
async def probar(p: Prueba):
    """Prueba una tienda (nueva o editada) sin guardarla ni anotarla en el historial."""
    return (await navegador.buscar([p.tienda], " ".join(p.q.split())))[0]


@app.get("/api/historial.csv")
def historial():
    if not HISTORIAL.exists():
        raise HTTPException(404, "Todavía no hay búsquedas.")
    return FileResponse(HISTORIAL, filename="historial-cotizaciones.csv", media_type="text/csv")


def main():
    global navegador
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ver", action="store_true", help="mostrar la ventana de Chrome")
    ap.add_argument("--puerto", type=int, default=PUERTO)
    ap.add_argument("--no-abrir", action="store_true", help="no abrir el navegador al arrancar")
    a = ap.parse_args()
    navegador = Navegador(visible=a.ver)
    if not a.no_abrir:
        import threading
        threading.Timer(3, lambda: webbrowser.open(f"http://localhost:{a.puerto}")).start()
    print(f"Cotizador en http://localhost:{a.puerto}  (Ctrl+C para cerrar)")
    import uvicorn
    # asyncio.run usa en Windows el loop que Playwright necesita para abrir Chrome.
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=a.puerto, log_level="warning"))
    asyncio.run(servidor.serve())


if __name__ == "__main__":
    main()
