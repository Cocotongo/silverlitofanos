import { Pedido } from '../pedidos/pedidos.service';

/**
 * Textos y detalles de pantalla propios de cada línea de producto.
 * Los componentes de cada línea (lo que se ve en "nuevo pedido" y en el detalle)
 * se eligen con @switch (pedido.linea) en las pantallas de pedidos.
 */
export interface LineaUI {
  subtitulo: (p: Pedido) => string;
  resumen: (p: Pedido) => string;
  generar: string;
  generando: string;
  descargar: string;
  mensaje: (p: Pedido) => string;
}

export const GENERICA: LineaUI = {
  subtitulo: (p) => p.producto,
  resumen: () => '',
  generar: 'Generar archivos',
  generando: 'Generando…',
  descargar: 'Descargar archivos',
  mensaje: (p) => `Hola ${p.cliente}, te comparto la vista previa de tu pedido #${p.id}.`,
};
