# SilVerLitofanos · App de pedidos

Controla los pedidos de lámparas con litofanos y genera el STL de la foto de cada cliente.

- **frontend/**: Angular 21 (lista de pedidos, nuevo pedido con foto, detalle con vista previa, descarga de STL y botón de WhatsApp).
- **backend/**: Python + FastAPI + SQLite. Guarda pedidos y archivos en `backend/datos/`.

## Líneas de producto
SilVer está separado en un **núcleo** común y **líneas de producto**:

- `backend/app/nucleo/`: lo que es igual en cualquier venta: pedidos, cliente, precio y anticipo, fecha de entrega, archivo del cliente y fases generales (nuevo, diseño, aprobado, producción, listo, entregado, cancelado).
- `backend/app/lineas/<linea>/`: lo propio de cada producto: qué datos pide (`config`), su catálogo, los pasos de su flujo (cada paso cae en una fase general) y cómo genera los archivos de producción. Hoy existe `litofano/` (el generador STL está en `lineas/litofano/generador.py`).
- `frontend/src/app/lineas/`: las piezas de pantalla de cada línea (en litofanos: encuadre de la foto, forma, material y medidas).

Para agregar una línea (por ejemplo letreros LED): crea `backend/app/lineas/letreros/` con una clase que herede de `Linea` (ver `lineas/base.py`), regístrala en `lineas/__init__.py`, y agrega sus textos en `frontend/src/app/lineas/registro.ts` y sus componentes en los `@switch` de `pedidos/`.

### Letreros LED (`lineas/letrero/`)
Del texto, la fuente y el alto de letra salen las piezas listas para imprimir: carcasa (canal para la tira, pared, piso con colgador) y cubierta difusora por pieza. El letrero se corta solo en piezas que caben en la cama; donde el canal cruza el corte el LED pasa por ahí, y donde dos letras solo se tocan por la pared se abre un túnel en el piso.

Las piezas embonan con **colas de milano** en cada tramo de pared que cruza el corte (macho en una pieza, hembra en la otra, desde la parte de atrás hasta 25 mm, sin llegar al frente). Se arman deslizando una pieza sobre la otra desde atrás; el pegamento queda como refuerzo.

Todas las medidas (ancho de tira, holgura, alto del túnel, pared, cubierta, holgura entre piezas, tamaño máximo de pieza…) viven en **Perfiles LED** (menú superior), uno por tira o proveedor. El pedido elige su perfil y las medidas usadas quedan en `perfil.txt` dentro del ZIP. Las fuentes están en `backend/app/lineas/letrero/fuentes/` (Pacifico y Lobster, licencia OFL): para agregar otra, copia ahí su `.ttf`.

### Lámparas luna (`lineas/luna/`)
Esfera litofano con la superficie de la Luna; no lleva foto del cliente. El relieve sale de `luna.png`, una mezcla del albedo (LROC) y el relieve (LOLA) del [CGI Moon Kit de la NASA](https://svs.gsfc.nasa.gov/4720), de dominio público, así que las lámparas se pueden vender. Para regenerarlo: `python tools/preparar_luna.py`.

La esfera es hueca, con una **boca plana abajo** para la placa LED (diámetro editable en el pedido; mide la placa y deja 1–2 mm de holgura) y un anillo sólido de 6 mm alrededor para que sea rígida. La cara visible de la Luna queda hacia el frente del slicer. Se imprime con la boca sobre la cama, sin soportes, con brim. Productos: Ø150 ($699, ≈150 g PLA) y Ø100 ($499, ≈60 g).

Al arrancar, la base de datos de la versión anterior se pasa sola al formato nuevo (los pedidos existentes quedan como litofanos).

## Cotizador de materia prima (`cotizador/`)
Buscador aparte que compara precios de un insumo en varias tiendas (Mercado Libre, Amazon, AliExpress, Steren, Shop3D y las que agregues). Corre en tu PC con `python cotizador.py`; instrucciones en [cotizador/LEEME.md](cotizador/LEEME.md).

## Requisitos (Windows)
- Python 3.11 o más nuevo
- Node.js 22.12 o más nuevo

## Arrancar

En una terminal, el backend:
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

En otra terminal, el frontend:
```
cd frontend
npm install
npm start
```

Abre http://localhost:4200

## Flujo de un pedido
1. **Nuevo pedido**: foto, cliente, producto, material, precio y anticipo.
2. **Encuadre**: en el detalle del pedido, acerca y mueve la foto con las barras; el recuadro naranja marca lo que se imprime y la prueba rápida muestra cómo se verá. "Mejorar contraste" (activo por defecto) saca detalle en caras y sombras. Dale **Guardar encuadre**.
3. **Generar STL**: crea el archivo y la vista previa encendida (5–15 s).
4. **WhatsApp**: abre el chat con el cliente para mandarle la vista previa.
5. Cambia el estado: Vista previa enviada → Aprobado → Imprimiendo → Listo → Entregado.
6. **Descargar STL** y ábrelo en Creality Print con el proceso "0.12mm Litofano PETG".

## Pruebas del backend
```
cd backend
pip install pytest httpx
python -m pytest
```

Catálogo y precios de litofanos: `productos` en `backend/app/lineas/litofano/__init__.py`.

## Automatización después de cada merge
- **Pruebas en GitHub** (`.github/workflows/pruebas.yml`): en cada PR y en cada push a `main` corren las pruebas del backend (`pytest`, Python 3.12) y el build del frontend (`npm run build`, Node 22). Si algo falla, el PR lo muestra en rojo antes de fusionarlo.
- **Despliegue solo en el servidor Docker** (`tools/actualizar_servidor.sh`): revisa si `main` tiene commits nuevos; si los tiene hace `git pull --ff-only` y `docker compose up -d --build`, si no, no hace nada. Ponlo en cron cada 5 minutos y cada merge queda desplegado a más tardar unos minutos después:
  ```
  */5 * * * * /ruta/a/silverlitofanos/tools/actualizar_servidor.sh >> $HOME/silver-actualizar.log 2>&1
  ```
  Los pedidos y archivos están en `./datos` (volumen del compose) y no se tocan. La rama se cambia con `SILVER_RAMA`.
