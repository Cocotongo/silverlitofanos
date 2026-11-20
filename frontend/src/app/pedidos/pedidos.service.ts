import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';

/** Fases generales, comunes a todas las líneas de producto. */
export type Fase = 'nuevo' | 'diseno' | 'aprobado' | 'produccion' | 'listo' | 'entregado' | 'cancelado';

export interface Paso {
  id: string;
  nombre: string;
  fase: Fase;
}

export interface Producto {
  id: string;
  nombre: string;
  precio: number;
  config: Record<string, unknown>;
}

export interface Linea {
  id: string;
  nombre: string;
  productos: Producto[];
  flujo: Paso[];
  archivo: { etiqueta: string; acepta: string; requerido: boolean } | null;
}

export interface Pedido<C = Record<string, any>> {
  id: number;
  linea: string;
  cliente: string;
  telefono: string;
  canal: string;
  producto: string;
  precio: number;
  anticipo: number;
  estado: string;
  notas: string;
  fecha_entrega: string | null;
  creado: string;
  archivo: string;
  config: C;
  generado: boolean;
  resumen: Record<string, any>;
}

export type PedidoCambios = Partial<Omit<Pedido, 'config'>> & { config?: Record<string, unknown> };

@Injectable({ providedIn: 'root' })
export class PedidosService {
  private http = inject(HttpClient);
  private api = '/api';

  /** Líneas de producto con su catálogo y su flujo de pasos. */
  lineas = toSignal(this.http.get<Linea[]>(`${this.api}/lineas`), { initialValue: [] });

  /** Todos los pasos de todas las líneas, sin repetir (para filtros). */
  pasos = computed(() => {
    const vistos = new Map<string, Paso>();
    for (const l of this.lineas()) for (const p of l.flujo) if (!vistos.has(p.id)) vistos.set(p.id, p);
    return [...vistos.values()];
  });

  linea(id: string) {
    return this.lineas().find((l) => l.id === id);
  }

  paso(pedido: Pick<Pedido, 'linea' | 'estado'>) {
    return this.linea(pedido.linea)?.flujo.find((p) => p.id === pedido.estado);
  }

  textoEstado(pedido: Pick<Pedido, 'linea' | 'estado'>) {
    return this.paso(pedido)?.nombre ?? pedido.estado;
  }

  listar(estado?: string) {
    const params = estado ? new HttpParams().set('estado', estado) : undefined;
    return this.http.get<Pedido[]>(`${this.api}/pedidos`, { params });
  }

  ver(id: number) {
    return this.http.get<Pedido>(`${this.api}/pedidos/${id}`);
  }

  crear(datos: FormData) {
    return this.http.post<Pedido>(`${this.api}/pedidos`, datos);
  }

  actualizar(id: number, cambios: PedidoCambios) {
    return this.http.patch<Pedido>(`${this.api}/pedidos/${id}`, cambios);
  }

  borrar(id: number) {
    return this.http.delete<void>(`${this.api}/pedidos/${id}`);
  }

  generar(id: number) {
    return this.http.post<Pedido>(`${this.api}/pedidos/${id}/generar`, {});
  }

  urlArchivo(id: number) {
    return `${this.api}/pedidos/${id}/archivo`;
  }

  urlPrevia(id: number, version = 0) {
    return `${this.api}/pedidos/${id}/previa?v=${version}`;
  }

  urlDescarga(id: number) {
    return `${this.api}/pedidos/${id}/descarga`;
  }
}
