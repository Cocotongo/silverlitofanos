import { Component, computed, effect, inject, input, output, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';

import { Pedido } from '../../pedidos/pedidos.service';
import { LineaUI } from '../lineas';
import { ConfigLetrero, LetreroService } from './letrero.service';

type PedidoLetrero = Pedido<ConfigLetrero>;

export const LETRERO_UI: LineaUI = {
  subtitulo: (p) => `«${p.config['texto']}» · ${String(p.config['fuente']).replace('-Regular', '')}`,
  resumen: (p) =>
    `${p.resumen['medidas']} · ${p.resumen['piezas']} piezas · ≈ ${p.resumen['gramos']} g · perfil ${p.resumen['perfil_nombre']}`,
  generar: 'Generar piezas',
  generando: 'Generando piezas…',
  descargar: 'Descargar STL',
  mensaje: (p) => `Hola ${p.cliente}, te comparto el diseño de tu letrero (pedido #${p.id}).`,
};

/** Texto, fuente, altura y perfil: en "nuevo pedido" y en el detalle. */
@Component({
  selector: 'app-letrero-campos',
  imports: [FormsModule],
  template: `
    <div><label>Texto del letrero</label>
      <input [ngModel]="valor().texto" (change)="poner('texto', $any($event.target).value)" maxlength="80" /></div>
    <div class="doble">
      <div>
        <label>Fuente</label>
        <select [ngModel]="valor().fuente" (ngModelChange)="poner('fuente', $event)">
          @for (f of fuentes(); track f) { <option [value]="f">{{ f.replace('-Regular', '') }}</option> }
        </select>
      </div>
      <div><label>Alto de letra (mm)</label>
        <input type="number" min="10" max="400" [ngModel]="valor().altura"
          (change)="poner('altura', +$any($event.target).value)" /></div>
    </div>
    <div>
      <label>Perfil de tira / proveedor</label>
      <select [ngModel]="valor().perfil_id ?? perfiles()[0]?.id" (ngModelChange)="poner('perfil_id', +$event)">
        @for (p of perfiles(); track p.id) {
          <option [value]="p.id">{{ p.nombre }} · tira {{ p.ancho_tira }} mm</option>
        }
      </select>
    </div>
  `,
  styles: `
    :host { display: grid; gap: 12px; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  `,
})
export class LetreroCampos {
  private servicio = inject(LetreroService);
  valor = input.required<ConfigLetrero>();
  cambio = output<Partial<ConfigLetrero>>();

  fuentes = toSignal(this.servicio.fuentes(), { initialValue: [] });
  perfiles = toSignal(this.servicio.perfiles(), { initialValue: [] });

  poner<K extends keyof ConfigLetrero>(campo: K, v: ConfigLetrero[K]) {
    if (v === this.valor()[campo]) return;
    this.cambio.emit({ [campo]: v } as Partial<ConfigLetrero>);
  }
}

/** Columna izquierda de "nuevo pedido": campos y vista previa en vivo. */
@Component({
  selector: 'app-letrero-nuevo',
  imports: [LetreroCampos],
  template: `
    <app-letrero-campos [valor]="valor()" (cambio)="cambiar($event)" />
    <figure>
      <img [src]="ensayo()" alt="Vista previa del letrero" (error)="sinVista.set(true)" (load)="sinVista.set(false)" />
      <figcaption>{{ sinVista() ? 'No se pudo dibujar: revisa el texto o la fuente' : 'Vista previa (azul = cortes y colas de milano)' }}</figcaption>
    </figure>
  `,
  styles: `
    :host { display: grid; gap: 12px; align-content: start; }
    figure { margin: 0; }
    img { width: 100%; border-radius: 8px; background: #16161a; min-height: 80px; }
    figcaption { font-size: .8rem; color: var(--suave); margin-top: 4px; text-align: center; }
  `,
})
export class LetreroNuevo {
  private servicio = inject(LetreroService);
  /** Valores iniciales del producto elegido (alto de letra). */
  base = input<Partial<ConfigLetrero>>({});
  config = output<Partial<ConfigLetrero>>();

  private cambios = signal<Partial<ConfigLetrero>>({ texto: 'SilVer', fuente: 'Pacifico-Regular' });
  valor = computed(() => ({ altura: 120, perfil_id: null, ...this.base(), ...this.cambios() }) as ConfigLetrero);
  ensayo = computed(() => this.servicio.urlEnsayo(this.valor()));
  sinVista = signal(false);

  constructor() {
    effect(() => this.config.emit(this.valor()));
  }

  cambiar(c: Partial<ConfigLetrero>) {
    this.cambios.update((v) => ({ ...v, ...c }));
  }
}

/** Detalle: vista previa (diseño o piezas generadas) y avisos. */
@Component({
  selector: 'app-letrero-vista',
  template: `
    @let p = pedido();
    <figure>
      <img [src]="p.generado ? '/api/pedidos/' + p.id + '/previa?v=' + version() : ensayo()" alt="Vista previa del letrero" />
      <figcaption>{{ p.generado ? 'Piezas generadas (azul = cortes y colas de milano)' : 'Vista previa rápida, todavía sin piezas' }}</figcaption>
    </figure>
    @if (p.generado) {
      <p class="nota">Piezas: {{ p.resumen['medidas_piezas']?.join(' · ') }} mm</p>
      @for (a of p.resumen['advertencias'] ?? []; track a) { <p class="aviso">⚠ {{ a }}</p> }
    }
  `,
  styles: `
    figure { margin: 0; }
    img { width: 100%; border-radius: 8px; background: #16161a; }
    figcaption { font-size: .8rem; color: var(--suave); margin-top: 4px; text-align: center; }
    .nota { color: var(--suave); font-size: .85rem; margin: 8px 0 0; }
    .aviso { color: #b7791f; font-size: .85rem; margin: 6px 0 0; }
  `,
})
export class LetreroVista {
  private servicio = inject(LetreroService);
  pedido = input.required<PedidoLetrero>();
  version = input(0);
  ensayo = computed(() => this.servicio.urlEnsayo(this.pedido().config) + `&v=${this.version()}`);
}
