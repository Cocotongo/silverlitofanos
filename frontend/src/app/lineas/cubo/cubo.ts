import { Component, computed, input, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Pedido } from '../../pedidos/pedidos.service';
import { LineaUI } from '../lineas';

export interface Encuadre {
  x: number;
  y: number;
  zoom: number;
}

export interface ConfigCubo {
  material: 'pla' | 'petg';
  lado: number;
  mejorar: boolean;
  encuadres: Encuadre[];
}

type PedidoCubo = Pedido<ConfigCubo>;

const CARAS = ['Frente', 'Derecha', 'Atrás', 'Izquierda'];

export const CUBO_UI: LineaUI = {
  subtitulo: (p) => `Cubo ${p.config['lado']} mm · ${String(p.config['material']).toUpperCase()}`,
  resumen: (p) =>
    `${p.resumen['medidas']} · caras ≈ ${p.resumen['gramos']} g de ${String(p.config['material']).toUpperCase()} blanco` +
    ` · base y tapa ≈ ${p.resumen['gramos_base_tapa']} g de PLA de color`,
  generar: 'Generar STL',
  generando: 'Generando STL…',
  descargar: 'Descargar STL (6 piezas)',
  mensaje: (p) => `Hola ${p.cliente}, te comparto cómo se verán las 4 caras de tu cubo (pedido #${p.id}).`,
};

/** Material y contraste. */
@Component({
  selector: 'app-cubo-campos',
  imports: [FormsModule],
  template: `
    @let c = valor();
    <div class="doble">
      <div>
        <label>Material de las caras</label>
        <select [ngModel]="c.material" (ngModelChange)="cambio.emit({ material: $event })">
          <option value="pla">PLA blanco</option>
          <option value="petg">PETG blanco</option>
        </select>
      </div>
      <div><label>Lado (mm)</label>
        <input type="number" min="50" max="150" [ngModel]="c.lado" (change)="lado($event)" /></div>
    </div>
    <label class="check">
      <input type="checkbox" [ngModel]="c.mejorar" (ngModelChange)="cambio.emit({ mejorar: $event })" />
      Mejorar contraste
    </label>
  `,
  styles: `
    :host { display: grid; gap: 12px; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .check { display: flex; gap: 8px; align-items: center; margin: 0; }
    .check input { width: auto; margin: 0; }
  `,
})
export class CuboCampos {
  valor = input.required<ConfigCubo>();
  cambio = output<Partial<ConfigCubo>>();

  lado(ev: Event) {
    const v = Number((ev.target as HTMLInputElement).value);
    if (!Number.isNaN(v)) this.cambio.emit({ lado: v });
  }
}

/** Las 4 fotos con su encuadre, y la vista previa encendida cuando ya se generó. */
@Component({
  selector: 'app-cubo-vista',
  template: `
    @let p = pedido();
    <div class="caras">
      @for (e of p.config.encuadres; track $index; let i = $index) {
        <figure>
          <div class="marco">
            <img [src]="'/api/pedidos/' + p.id + '/archivo?n=' + (i + 1)" alt="Foto {{ i + 1 }}"
              [style.object-position]="e.x * 100 + '% ' + e.y * 100 + '%'"
              [style.transform-origin]="e.x * 100 + '% ' + e.y * 100 + '%'" [style.transform]="'scale(' + e.zoom + ')'" />
          </div>
          <figcaption>{{ i + 1 }}. {{ caras[i] }}</figcaption>
          <label>Acercar <input type="range" min="1" max="4" step="0.05" [value]="e.zoom" (change)="poner(i, 'zoom', $event)" /></label>
          <label>Lados <input type="range" min="0" max="1" step="0.01" [value]="e.x" (change)="poner(i, 'x', $event)" /></label>
          <label>Altura <input type="range" min="0" max="1" step="0.01" [value]="e.y" (change)="poner(i, 'y', $event)" /></label>
        </figure>
      }
    </div>
    @if (p.generado) {
      <img class="previa" [src]="urlPrevia()" alt="Vista previa de las 4 caras encendidas" />
    }
  `,
  styles: `
    .caras { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
    figure { margin: 0; display: grid; gap: 4px; }
    .marco { aspect-ratio: 1; overflow: hidden; border-radius: 6px; background: #111; }
    .marco img { width: 100%; height: 100%; object-fit: cover; filter: grayscale(1); }
    figcaption { font-size: .8rem; color: var(--suave); text-align: center; }
    label { display: grid; grid-template-columns: 3.6em 1fr; gap: 4px; font-size: .75rem; align-items: center; margin: 0; }
    input[type=range] { width: 100%; }
    .previa { width: 100%; margin-top: 12px; border-radius: 8px; background: #111; }
    @media (max-width: 760px) { .caras { grid-template-columns: repeat(2, 1fr); } }
  `,
})
export class CuboVista {
  pedido = input.required<PedidoCubo>();
  version = input(0);
  cambio = output<Partial<ConfigCubo>>();
  caras = CARAS;
  urlPrevia = computed(() => `/api/pedidos/${this.pedido().id}/previa?v=${this.version()}`);

  poner(i: number, campo: keyof Encuadre, ev: Event) {
    const v = Number((ev.target as HTMLInputElement).value);
    const encuadres = this.pedido().config.encuadres.map((e, j) => (j === i ? { ...e, [campo]: v } : e));
    this.cambio.emit({ encuadres });
  }
}
