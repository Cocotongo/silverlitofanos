import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';

export interface ConfigLetrero {
  texto: string;
  fuente: string;
  altura: number;
  perfil_id: number | null;
}

/** Medidas de construcción del letrero; cambian si cambia el proveedor de la tira. */
export interface PerfilLed {
  id: number;
  nombre: string;
  proveedor: string;
  ancho_tira: number;
  holgura_tira: number;
  alto_tunel: number;
  profundidad: number;
  base: number;
  fondo_canal: number;
  pared: number;
  escalon: number;
  tapa_pared: number;
  tapa_frente: number;
  tapa_holgura: number;
  holgura_union: number;
  pieza_max: number;
  colgador_diam: number;
  colgador_largo: number;
  cable_ancho: number;
  cable_largo: number;
}

/** Campos del perfil agrupados para la pantalla de edición. */
export const CAMPOS_PERFIL: { grupo: string; campos: { id: keyof PerfilLed; texto: string }[] }[] = [
  {
    grupo: 'Tira LED (depende del proveedor)',
    campos: [
      { id: 'ancho_tira', texto: 'Ancho de la tira' },
      { id: 'holgura_tira', texto: 'Holgura por lado de la tira' },
      { id: 'alto_tunel', texto: 'Alto del túnel entre letras' },
    ],
  },
  {
    grupo: 'Carcasa',
    campos: [
      { id: 'profundidad', texto: 'Profundidad total' },
      { id: 'base', texto: 'Piso (contra la pared)' },
      { id: 'fondo_canal', texto: 'Altura del canal (asiento de la cubierta)' },
      { id: 'pared', texto: 'Grosor del contorno' },
      { id: 'escalon', texto: 'Escalón para la cubierta, por lado' },
    ],
  },
  {
    grupo: 'Cubierta difusora',
    campos: [
      { id: 'tapa_pared', texto: 'Pared' },
      { id: 'tapa_frente', texto: 'Frente' },
      { id: 'tapa_holgura', texto: 'Holgura con la carcasa' },
    ],
  },
  {
    grupo: 'Piezas y montaje',
    campos: [
      { id: 'pieza_max', texto: 'Medida máxima de pieza (cama)' },
      { id: 'holgura_union', texto: 'Holgura entre piezas' },
      { id: 'colgador_diam', texto: 'Colgador: diámetro' },
      { id: 'colgador_largo', texto: 'Colgador: largo' },
      { id: 'cable_ancho', texto: 'Salida de cable: ancho' },
      { id: 'cable_largo', texto: 'Salida de cable: largo' },
    ],
  },
];

@Injectable({ providedIn: 'root' })
export class LetreroService {
  private http = inject(HttpClient);
  private api = '/api/lineas/letrero';

  fuentes() {
    return this.http.get<string[]>(`${this.api}/fuentes`);
  }

  perfiles() {
    return this.http.get<PerfilLed[]>(`${this.api}/perfiles`);
  }

  crearPerfil(datos: Partial<PerfilLed>) {
    return this.http.post<PerfilLed>(`${this.api}/perfiles`, datos);
  }

  editarPerfil(id: number, datos: Partial<PerfilLed>) {
    return this.http.patch<PerfilLed>(`${this.api}/perfiles/${id}`, datos);
  }

  borrarPerfil(id: number) {
    return this.http.delete<void>(`${this.api}/perfiles/${id}`);
  }

  urlEnsayo(c: Partial<ConfigLetrero>) {
    let q = new HttpParams().set('texto', c.texto || ' ').set('fuente', c.fuente ?? '').set('altura', c.altura ?? 120);
    if (c.perfil_id) q = q.set('perfil_id', c.perfil_id);
    return `${this.api}/ensayo?${q}`;
  }
}
