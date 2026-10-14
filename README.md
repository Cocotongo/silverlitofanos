# SilVerLitofanos · App de pedidos

Controla los pedidos de lámparas con litofanos y genera el STL de la foto de cada cliente.

- **frontend/**: Angular 21 (lista de pedidos, nuevo pedido con foto, detalle con vista previa, descarga de STL y botón de WhatsApp).
- **backend/**: Python + FastAPI + SQLite. Guarda pedidos y fotos en `backend/datos/` y genera el STL con `app/litofano.py`.

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
2. **Generar STL**: crea el archivo y la vista previa encendida (5–15 s).
3. **WhatsApp**: abre el chat con el cliente para mandarle la vista previa.
4. Cambia el estado: Vista previa enviada → Aprobado → Imprimiendo → Listo → Entregado.
5. **Descargar STL** y ábrelo en Creality Print con el proceso "0.12mm Litofano PETG".

## Pruebas del backend
```
cd backend
pip install pytest httpx
python -m pytest
```

Catálogo y precios: lista `PRODUCTOS` en `backend/app/main.py`.
