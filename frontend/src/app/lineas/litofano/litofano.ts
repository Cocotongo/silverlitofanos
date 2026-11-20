import { Component, computed, effect, input, output, signal } from '@angular/core';
import { HttpParams } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

import { Pedido } from '../../pedidos/pedidos.service';
import { LineaUI } from '../lineas';

export interface ConfigLitofano {
  forma: 'panel' | 'cilindro';
  material: 'pla' | 'petg';
  ancho: number;
  diametro: number;
  alto: number;
  encuadre_x: number;
  encuadre_y: number;
  zoom: number;
  mejorar: boolean;
}

type PedidoLitofano = Pedido<ConfigLitofano>;

interface Encuadre {
  x: number;
  y: number;
  zoom: number;
  mejorar: boolean;
}

const urlEnsayo = (id: number, a: Encuadre, version = 0) => {
  const q = new HttpParams({ fromObject: { x: a.x, y: a.y, zoom: a.zoom, mejorar: a.mejorar, v: version } });
  return `/api/lineas/litofano/pedidos/${id}/ensayo?${q}`;
};

export const LITOFANO_UI: LineaUI = {
  subtitulo: (p) => `${p.config['forma'] === 'panel' ? 'Panel' : 'Cilindro'} · ${String(p.config['material']).toUpperCase()}`,
  resumen: (p) => `${p.resumen['medidas']} · ≈ ${p.resumen['gramos']} g de ${String(p.config['material']).toUpperCase()}`,
  generar: 'Generar STL',
  generando: 'Generando STL…',
  descargar: 'Descargar STL',
  mensaje: (p) => `Hola ${p.cliente}, te comparto la vista previa de tu lámpara (pedido #${p.id}).`,
};

/** Datos propios del litofano al crear el pedido. */
@Component({
  selector: 'app-litofano-nuevo',
  imports: [FormsModule],
  template: `
    <div>
      <label>Material</label>
      <select [ngModel]="material()" (ngModelChange)="material.set($event)">
        <option value="petg">PETG blanco</option>
        <option value="pla">PLA blanco</option>
      </select>
    </div>
  `,
})
export class LitofanoNuevo {
  config = output<Partial<ConfigLitofano>>();
  material = signal<'petg' | 'pla'>('petg');

  constructor() {
    effect(() => this.config.emit({ material: this.material() }));
  }
}

/** Foto, recuadro de encuadre y prueba rápida / vista previa encendida. */
@Component({
  selector: 'app-litofano-vista',
  template: `
    @let p = pedido();
    <div class="imagenes">
      <figure>
        <div class="marco-foto">
          <img class="original" [src]="urlFoto()" alt="Foto original" (load)="medirFoto($event)" />
          @if (recorte(); as r) {
            <div class="recorte" [style.left.%]="r.izq" [style.top.%]="r.arr"
              [style.width.%]="r.ancho" [style.height.%]="r.alto"></div>
          }
        </div>
        <figcaption>Foto original (el recuadro es lo que se imprime)</figcaption>
      </figure>
      <figure>
        @if (p.generado && !pendiente()) {
          <img [src]="urlPrevia()" alt="Vista previa encendida" />
          <figcaption>Así se verá encendido</figcaption>
        } @else {
          <img [src]="ensayoUrl()" alt="Prueba de encuadre" />
          <figcaption>Prueba rápida de encuadre</figcaption>
        }
      </figure>
    </div>

    <div class="encuadre">
      <div><label>Acercar ({{ ajuste().zoom.toFixed(1) }}×)</label>
        <input type="range" min="1" max="4" step="0.1" [value]="ajuste().zoom"
          (input)="mover('zoom', $event)" (change)="probar()" /></div>
      <div><label>Mover a los lados</label>
        <input type="range" min="0" max="1" step="0.01" [value]="ajuste().x"
          (input)="mover('x', $event)" (change)="probar()" /></div>
      <div><label>Mover arriba / abajo</label>
        <input type="range" min="0" max="1" step="0.01" [value]="ajuste().y"
          (input)="mover('y', $event)" (change)="probar()" /></div>
      <label class="casilla">
        <input type="checkbox" [checked]="ajuste().mejorar" (change)="cambiarMejorar($event)" />
        Mejorar contraste (saca detalle en caras y sombras)
      </label>
      @if (pendiente()) {
        <div class="acciones">
          <button (click)="guardarEncuadre()">Guardar encuadre</button>
          <button class="secundario" (click)="deshacerEncuadre()">Deshacer</button>
        </div>
      }
    </div>
  `,
  styles: `
    .imagenes { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    figure { margin: 0; }
    figure img { width: 100%; aspect-ratio: 3 / 2; object-fit: contain; border-radius: 8px; background: #111; }
    .original { filter: grayscale(1); }
    .marco-foto { position: relative; line-height: 0; overflow: hidden; border-radius: 8px; }
    .marco-foto img { aspect-ratio: auto; object-fit: fill; display: block; }
    .recorte { position: absolute; border: 2px solid var(--acento); border-radius: 4px;
      box-shadow: 0 0 0 9999px rgb(0 0 0 / .45); pointer-events: none; }
    .encuadre { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 14px; }
    .encuadre input[type='range'] { padding: 0; accent-color: var(--acento); }
    .encuadre .casilla, .encuadre .acciones { grid-column: 1 / -1; }
    .casilla { display: flex; gap: 8px; align-items: center; color: var(--texto); font-size: .9rem; margin: 0; }
    .casilla input { width: auto; }
    figcaption { font-size: .8rem; color: var(--suave); margin-top: 4px; text-align: center; }
    .acciones { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
    @media (max-width: 760px) { .encuadre { grid-template-columns: 1fr; } }
  `,
})
export class LitofanoVista {
  pedido = input.required<PedidoLitofano>();
  version = input(0);
  cambio = output<Partial<ConfigLitofano>>();

  // encuadre que se esta moviendo (ajuste) y el que se manda a la prueba rapida (ensayo)
  ajuste = signal<Encuadre>({ x: 0.5, y: 0.5, zoom: 1, mejorar: true });
  ensayo = signal<Encuadre>({ x: 0.5, y: 0.5, zoom: 1, mejorar: true });
  private tamFoto = signal<{ w: number; h: number } | null>(null);

  urlFoto = computed(() => `/api/pedidos/${this.pedido().id}/archivo`);
  urlPrevia = computed(() => `/api/pedidos/${this.pedido().id}/previa?v=${this.version()}`);
  ensayoUrl = computed(() => urlEnsayo(this.pedido().id, this.ensayo(), this.version()));

  pendiente = computed(() => {
    const c = this.pedido().config;
    const a = this.ajuste();
    return a.x !== c.encuadre_x || a.y !== c.encuadre_y || a.zoom !== c.zoom || a.mejorar !== c.mejorar;
  });

  // recuadro sobre la foto, en % (misma cuenta que encuadrar() en el backend)
  recorte = computed(() => {
    const c = this.pedido().config;
    const f = this.tamFoto();
    if (!f) return null;
    const a = this.ajuste();
    const r = c.forma === 'panel' ? f.w / f.h : (Math.PI * c.diametro) / c.alto;
    let [cw, ch] = f.w / f.h > r ? [f.h * r, f.h] : [f.w, f.w / r];
    cw /= a.zoom;
    ch /= a.zoom;
    const izq = Math.min(Math.max(a.x * f.w - cw / 2, 0), f.w - cw);
    const arr = Math.min(Math.max(a.y * f.h - ch / 2, 0), f.h - ch);
    return { izq: (izq / f.w) * 100, arr: (arr / f.h) * 100, ancho: (cw / f.w) * 100, alto: (ch / f.h) * 100 };
  });

  private ultimoId = 0;

  constructor() {
    // al abrir otro pedido, el encuadre arranca con lo guardado
    effect(() => {
      const p = this.pedido();
      if (p.id !== this.ultimoId) {
        this.ultimoId = p.id;
        this.deshacerEncuadre();
      }
    });
  }

  medirFoto(ev: Event) {
    const img = ev.target as HTMLImageElement;
    this.tamFoto.set({ w: img.naturalWidth, h: img.naturalHeight });
  }

  mover(campo: 'x' | 'y' | 'zoom', ev: Event) {
    const valor = Number((ev.target as HTMLInputElement).value);
    this.ajuste.update((a) => ({ ...a, [campo]: valor }));
  }

  cambiarMejorar(ev: Event) {
    this.ajuste.update((a) => ({ ...a, mejorar: (ev.target as HTMLInputElement).checked }));
    this.probar();
  }

  probar() {
    this.ensayo.set(this.ajuste());
  }

  guardarEncuadre() {
    const a = this.ajuste();
    this.cambio.emit({ encuadre_x: a.x, encuadre_y: a.y, zoom: a.zoom, mejorar: a.mejorar });
  }

  deshacerEncuadre() {
    const c = this.pedido().config;
    this.ajuste.set({ x: c.encuadre_x, y: c.encuadre_y, zoom: c.zoom, mejorar: c.mejorar });
    this.probar();
  }
}

/** Forma, material y medidas del litofano (columna de datos del pedido). */
@Component({
  selector: 'app-litofano-campos',
  imports: [FormsModule],
  template: `
    @let c = pedido().config;
    <div class="doble">
      <div>
        <label>Forma</label>
        <select [ngModel]="c.forma" (ngModelChange)="cambio.emit({ forma: $event })">
          <option value="panel">Panel</option>
          <option value="cilindro">Cilindro</option>
        </select>
      </div>
      <div>
        <label>Material</label>
        <select [ngModel]="c.material" (ngModelChange)="cambio.emit({ material: $event })">
          <option value="petg">PETG</option>
          <option value="pla">PLA</option>
        </select>
      </div>
    </div>
    @if (c.forma === 'panel') {
      <div><label>Ancho (mm)</label>
        <input type="number" [ngModel]="c.ancho" (change)="numero('ancho', $event)" /></div>
    } @else {
      <div class="doble">
        <div><label>Diámetro (mm)</label>
          <input type="number" [ngModel]="c.diametro" (change)="numero('diametro', $event)" /></div>
        <div><label>Alto (mm)</label>
          <input type="number" [ngModel]="c.alto" (change)="numero('alto', $event)" /></div>
      </div>
    }
  `,
  styles: `
    :host { display: grid; gap: 12px; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  `,
})
export class LitofanoCampos {
  pedido = input.required<PedidoLitofano>();
  cambio = output<Partial<ConfigLitofano>>();

  numero(campo: 'ancho' | 'diametro' | 'alto', ev: Event) {
    const valor = Number((ev.target as HTMLInputElement).value);
    if (!Number.isNaN(valor)) this.cambio.emit({ [campo]: valor });
  }
}
