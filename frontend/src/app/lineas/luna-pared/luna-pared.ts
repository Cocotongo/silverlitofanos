import { Component, computed, effect, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { LineaUI } from '../lineas';

export interface ConfigLunaPared {
  material: 'pla' | 'petg';
  diametro: number;
  alto_relieve: number;
}

export const LUNA_PARED_UI: LineaUI = {
  subtitulo: (p) => `Luna de pared Ø${Number(p.config['diametro']) / 10} cm · ${String(p.config['material']).toUpperCase()}`,
  resumen: (p) =>
    `${p.resumen['medidas']} · losetas ≈ ${p.resumen['gramos']} g, marco ≈ ${p.resumen['gramos_marco']} g, ` +
    `aro ≈ ${p.resumen['gramos_aro']} g · tira LED ${p.resumen['tira_cm']} cm`,
  generar: 'Generar piezas',
  generando: 'Generando las 12 piezas…',
  descargar: 'Descargar ZIP',
  mensaje: (p) => `Hola ${p.cliente}, así se verá tu luna de pared encendida (pedido #${p.id}).`,
};

/** Material, diámetro y qué tanto sobresale el relieve. */
@Component({
  selector: 'app-luna-pared-campos',
  imports: [FormsModule],
  template: `
    @let c = valor();
    <div class="doble">
      <div>
        <label>Material de las losetas</label>
        <select [ngModel]="c.material" (ngModelChange)="cambio.emit({ material: $event })">
          <option value="pla">PLA blanco</option>
          <option value="petg">PETG blanco</option>
        </select>
      </div>
      <div><label>Diámetro (mm)</label>
        <input type="number" min="200" max="410" [ngModel]="c.diametro" (change)="numero('diametro', $event)" /></div>
    </div>
    <div><label>Alto del relieve (mm)</label>
      <input type="number" min="2" max="8" step="0.5" [ngModel]="c.alto_relieve" (change)="numero('alto_relieve', $event)" />
      <small>Más alto = cráteres más marcados con la luz de lado, pero más filamento.</small></div>
  `,
  styles: `
    :host { display: grid; gap: 12px; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    small { color: var(--suave); font-size: .8rem; }
  `,
})
export class LunaParedCampos {
  valor = input.required<ConfigLunaPared>();
  cambio = output<Partial<ConfigLunaPared>>();

  numero(campo: 'diametro' | 'alto_relieve', ev: Event) {
    const v = Number((ev.target as HTMLInputElement).value);
    if (!Number.isNaN(v)) this.cambio.emit({ [campo]: v });
  }
}

/** Columna izquierda de "nuevo pedido": no lleva foto, solo medidas. */
@Component({
  selector: 'app-luna-pared-nuevo',
  imports: [LunaParedCampos],
  template: `
    <p class="nota">La luna de pared no necesita foto del cliente: el relieve sale del mapa de alturas de la NASA.</p>
    <app-luna-pared-campos [valor]="valor()" (cambio)="cambiar($event)" />
  `,
  styles: `
    :host { display: grid; gap: 12px; align-content: start; }
    .nota { color: var(--suave); margin: 0; }
  `,
})
export class LunaParedNuevo {
  base = input<Partial<ConfigLunaPared>>({});
  config = output<Partial<ConfigLunaPared>>();

  private cambios = signal<Partial<ConfigLunaPared>>({});
  valor = computed(
    () => ({ material: 'pla', diametro: 400, alto_relieve: 5, ...this.base(), ...this.cambios() }) as ConfigLunaPared,
  );

  constructor() {
    effect(() => this.config.emit(this.valor()));
  }

  cambiar(c: Partial<ConfigLunaPared>) {
    this.cambios.update((v) => ({ ...v, ...c }));
  }
}
