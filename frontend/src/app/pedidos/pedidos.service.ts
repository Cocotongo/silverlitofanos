import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export type Estado =
  | 'nuevo' | 'previa_enviada' | 'aprobado' | 'imprimiendo' | 'listo' | 'entregado' | 'cancelado';

export const ESTADOS: { valor: Estado; texto: string }[] = [
  { valor: 'nuevo', texto: 'Nuevo' },
  { valor: 'previa_enviada', texto: 'Vista previa enviada' },
  { valor: 'aprobado', texto: 'Aprobado' },
  { valor: 'imprimiendo', texto: 'Imprimiendo' },
  { valor: 'listo', texto: 'Listo para entregar' },
  { valor: 'entregado', texto: 'Entregado' },
  { valor: 'cancelado', texto: 'Cancelado' },
];

export const textoEstado = (e: Estado) => ESTADOS.find((x) => x.valor === e)?.texto ?? e;

export interface Producto {
  id: string;
  nombre: string;
  forma: 'panel' | 'cilindro';
  precio: number;
  ancho?: number;
  diametro?: number;
  alto?: number;
}

export interface Pedido {
  id: number;
  cliente: string;
  telefono: string;
  canal: string;
  producto: string;
  forma: 'panel' | 'cilindro';
  material: 'pla' | 'petg';
  ancho: number;
  diametro: number;
  alto: number;
  encuadre_x: number;
  encuadre_y: number;
  zoom: number;
  mejorar: boolean;
  precio: number;
  anticipo: number;
  estado: Estado;
  notas: string;
  fecha_entrega: string | null;
  creado: string;
  stl_listo: boolean;
  gramos: number | null;
  medidas: string;
}

export interface Encuadre {
  x: number;
  y: number;
  zoom: number;
  mejorar: boolean;
}

@Injectable({ providedIn: 'root' })
export class PedidosService {
  private http = inject(HttpClient);
  private api = '/api';

  productos() {
    return this.http.get<Producto[]>(`${this.api}/productos`);
  }

  listar(estado?: Estado | '') {
    const params = estado ? new HttpParams().set('estado', estado) : undefined;
    return this.http.get<Pedido[]>(`${this.api}/pedidos`, { params });
  }

  ver(id: number) {
    return this.http.get<Pedido>(`${this.api}/pedidos/${id}`);
  }

  crear(datos: FormData) {
    return this.http.post<Pedido>(`${this.api}/pedidos`, datos);
  }

  actualizar(id: number, cambios: Partial<Pedido>) {
    return this.http.patch<Pedido>(`${this.api}/pedidos/${id}`, cambios);
  }

  borrar(id: number) {
    return this.http.delete<void>(`${this.api}/pedidos/${id}`);
  }

  generar(id: number) {
    return this.http.post<Pedido>(`${this.api}/pedidos/${id}/generar`, {});
  }

  urlFoto(id: number) {
    return `${this.api}/pedidos/${id}/foto`;
  }

  urlPrevia(id: number, version = 0) {
    return `${this.api}/pedidos/${id}/previa?v=${version}`;
  }

  urlEnsayo(id: number, a: Encuadre, version = 0) {
    const q = new HttpParams({ fromObject: { x: a.x, y: a.y, zoom: a.zoom, mejorar: a.mejorar, v: version } });
    return `${this.api}/pedidos/${id}/ensayo?${q}`;
  }

  urlStl(id: number) {
    return `${this.api}/pedidos/${id}/stl`;
  }
}
