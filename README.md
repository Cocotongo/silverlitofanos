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

Catálogo y precios: lista `PRODUCTOS` en `backend/app/main.py`.
