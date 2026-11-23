import { Component, computed, effect, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { LineaUI } from '../lineas';

export interface ConfigLuna {
  material: 'pla' | 'petg';
  diametro: number;
  abertura: number;
}

export const LUNA_UI: LineaUI = {
  subtitulo: (p) => `Luna Ø${p.config['diametro']} mm · ${String(p.config['material']).toUpperCase()}`,
  resumen: (p) => `${p.resumen['medidas']} · ≈ ${p.resumen['gramos']} g de ${String(p.config['material']).toUpperCase()}`,
  generar: 'Generar STL',
  generando: 'Generando STL…',
  descargar: 'Descargar STL',
  mensaje: (p) => `Hola ${p.cliente}, así se verá tu lámpara luna encendida (pedido #${p.id}).`,
};

/** Material, diámetro y boca para la placa LED. */
@Component({
  selector: 'app-luna-campos',
  imports: [FormsModule],
  template: `
    @let c = valor();
    <div class="doble">
      <div>
        <label>Material</label>
        <select [ngModel]="c.material" (ngModelChange)="cambio.emit({ material: $event })">
          <option value="pla">PLA blanco</option>
          <option value="petg">PETG blanco</option>
        </select>
      </div>
      <div><label>Diámetro (mm)</label>
        <input type="number" min="60" max="200" [ngModel]="c.diametro" (change)="numero('diametro', $event)" /></div>
    </div>
    <div><label>Boca para la placa LED (mm)</label>
      <input type="number" min="15" max="80" [ngModel]="c.abertura" (change)="numero('abertura', $event)" />
      <small>Mide la placa LED y deja 1–2 mm de holgura.</small></div>
  `,
  styles: `
    :host { display: grid; gap: 12px; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    small { color: var(--suave); font-size: .8rem; }
  `,
})
export class LunaCampos {
  valor = input.required<ConfigLuna>();
  cambio = output<Partial<ConfigLuna>>();

  numero(campo: 'diametro' | 'abertura', ev: Event) {
    const v = Number((ev.target as HTMLInputElement).value);
    if (!Number.isNaN(v)) this.cambio.emit({ [campo]: v });
  }
}

/** Columna izquierda de "nuevo pedido": la luna no lleva foto, solo medidas. */
@Component({
  selector: 'app-luna-nuevo',
  imports: [LunaCampos],
  template: `
    <p class="nota">La lámpara luna no necesita foto del cliente: se genera con la superficie de la Luna (mapas de la NASA).</p>
    <app-luna-campos [valor]="valor()" (cambio)="cambiar($event)" />
  `,
  styles: `
    :host { display: grid; gap: 12px; align-content: start; }
    .nota { color: var(--suave); margin: 0; }
  `,
})
export class LunaNuevo {
  /** Valores iniciales del producto elegido (diámetro). */
  base = input<Partial<ConfigLuna>>({});
  config = output<Partial<ConfigLuna>>();

  private cambios = signal<Partial<ConfigLuna>>({});
  valor = computed(() => ({ material: 'pla', diametro: 150, abertura: 40, ...this.base(), ...this.cambios() }) as ConfigLuna);

  constructor() {
    effect(() => this.config.emit(this.valor()));
  }

  cambiar(c: Partial<ConfigLuna>) {
    this.cambios.update((v) => ({ ...v, ...c }));
  }
}
