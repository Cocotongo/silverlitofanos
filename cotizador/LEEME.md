# Cotizador de materia prima

Buscador tipo Google para materia prima: escribes lo que necesitas (por ejemplo
`filamento pla blanco 1kg` o `tira led cob usb`) y busca al mismo tiempo en las tiendas
que tengas definidas. Te da el más barato de cada tienda y una tabla de todos los
productos de menor a mayor precio, con enlace a cada uno.

Tiendas que trae listas: **Mercado Libre, Amazon México, AliExpress, Steren y Shop3D**.
Puedes agregar, quitar o apagar tiendas en la pestaña **Tiendas** (se guardan en `tiendas.json`).

## Cómo funciona
Abre la página de búsqueda de cada tienda con un Chrome propio, sin ventana, y lee
los productos con selectores CSS (como lo haría una persona viendo la página). Por eso
corre en tu PC: las tiendas bloquean a los servidores, pero no a un Chrome en casa.

- El Chrome usa un perfil aparte (`datos/perfil-chrome`), no toca tu Chrome de diario.
- Cada búsqueda queda guardada en `datos/historial.csv` (botón "Historial (CSV)"), para
  ver cómo cambian los precios con el tiempo. Se abre en Excel.

## Instalar (una vez, en Windows)
```
cd C:\SilVer\silverlitofanos\cotizador
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Usa el Google Chrome que ya tienes instalado. Si no lo encuentra, instala el de Playwright:
`python -m playwright install chromium`.

## Usar
```
cd C:\SilVer\silverlitofanos\cotizador
.venv\Scripts\activate
python cotizador.py
```
Se abre http://localhost:8765. Escribe y dale **Buscar** (tarda de 10 a 30 segundos).

- **Solo los que tengan todas las palabras** quita lo que no viene al caso (si buscas
  "pla blanco", deja fuera el PLA rojo). Desmárcalo si una tienda escribe distinto el nombre.
- **Precio mínimo / máximo** filtra sin volver a buscar.
- Si una tienda sale vacía o pide "no soy robot", arranca con `python cotizador.py --ver`,
  resuelve la verificación en la ventana de Chrome una vez y vuelve a buscar. Queda guardado.

## Agregar una tienda
En **Tiendas → + Agregar tienda**:
1. **URL de búsqueda**: busca algo en la tienda, copia la dirección y cambia lo que
   escribiste por `{q+}` (palabras unidas con +), `{q-}` (con guiones) o `{q}`.
   Ej. `https://shop3d.mx/?s={q+}&post_type=product`.
2. **Selectores**: en la tienda, clic derecho sobre un producto → Inspeccionar. Necesitas
   la clase que se repite en cada tarjeta de producto (**Producto**), la del nombre
   (**Título**) y la del precio (**Precio**). Si pones varios separados por coma se prueban
   en orden. Para tiendas WooCommerce (muy comunes en México) usa **Plantilla WooCommerce**.
3. **Probar** con lo que tengas escrito en el buscador y, si sale bien, **Guardar tiendas**.

Si una tienda cambia su página y deja de salir, normalmente basta con actualizar el
selector de Producto o Precio.

## Notas
- Los precios no incluyen envío. En AliExpress y Mercado Libre el precio puede ser
  "desde" (varía por color o tamaño): revisa en la tienda antes de comprar.
- Mercado Libre y Amazon mezclan anuncios patrocinados en los resultados; salen igual
  que los demás.
