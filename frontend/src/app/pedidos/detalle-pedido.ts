import { Component, computed, inject, input, numberAttribute, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { CuboCampos, CuboVista } from '../lineas/cubo/cubo';
import { LetreroCampos, LetreroVista } from '../lineas/letrero/letrero';
import { LitofanoCampos, LitofanoVista } from '../lineas/litofano/litofano';
import { LunaCampos } from '../lineas/luna/luna';
import { LunaParedCampos } from '../lineas/luna-pared/luna-pared';
import { lineaUI } from '../lineas/registro';
import { Pedido, PedidoCambios, PedidosService } from './pedidos.service';

@Component({
  selector: 'app-detalle-pedido',
  imports: [CurrencyPipe, DatePipe, FormsModule, RouterLink, LitofanoVista, LitofanoCampos, LetreroVista, LetreroCampos, LunaCampos, LunaParedCampos, CuboCampos, CuboVista],
  template: `
    <a routerLink="/pedidos">← Pedidos</a>
    @if (pedido(); as p) {
      <div class="titulo">
        <h1>#{{ p.id }} · {{ p.cliente }}</h1>
        <span class="estado {{ p.estado }}">{{ servicio.textoEstado(p) }}</span>
      </div>

      <div class="rejilla">
        <div class="tarjeta">
          @switch (p.linea) {
            @case ('litofano') {
              <app-litofano-vista [pedido]="$any(p)" [version]="version()" (cambio)="cambiarConfig($event)" />
            }
            @case ('letrero') {
              <app-letrero-vista [pedido]="$any(p)" [version]="version()" />
            }
            @case ('cubo') {
              <app-cubo-vista [pedido]="$any(p)" [version]="version()" (cambio)="cambiarConfig($event)" />
            }
            @default {
              @if (p.generado) {
                <img class="previa" [src]="servicio.urlPrevia(p.id, version())" alt="Vista previa" />
              }
            }
          }

          <div class="acciones">
            <button (click)="generar()" [disabled]="generando()">
              {{ generando() ? ui().generando : p.generado ? 'Volver a generar' : ui().generar }}
            </button>
            @if (p.generado) {
              <a class="boton" [href]="servicio.urlDescarga(p.id)">{{ ui().descargar }}</a>
            }
            @if (whatsapp(); as w) {
              <a class="boton verde" [href]="w" target="_blank" rel="noopener">WhatsApp</a>
            }
          </div>
          @if (p.generado && ui().resumen(p); as r) {
            <p class="nota">{{ r }}</p>
          }
          @if (error()) { <p class="error">{{ error() }}</p> }
        </div>

        <div class="tarjeta datos">
          <div>
            <label>Estado</label>
            <select [ngModel]="p.estado" (ngModelChange)="cambiar({ estado: $event })">
              @for (e of servicio.linea(p.linea)?.flujo; track e.id) { <option [value]="e.id">{{ e.nombre }}</option> }
            </select>
          </div>
          @switch (p.linea) {
            @case ('litofano') { <app-litofano-campos [pedido]="$any(p)" (cambio)="cambiarConfig($event)" /> }
            @case ('letrero') { <app-letrero-campos [valor]="$any(p.config)" (cambio)="cambiarConfig($event)" /> }
            @case ('luna') { <app-luna-campos [valor]="$any(p.config)" (cambio)="cambiarConfig($event)" /> }
            @case ('luna_pared') { <app-luna-pared-campos [valor]="$any(p.config)" (cambio)="cambiarConfig($event)" /> }
            @case ('cubo') { <app-cubo-campos [valor]="$any(p.config)" (cambio)="cambiarConfig($event)" /> }
          }
          <div class="doble">
            <div><label>Precio</label>
              <input type="number" [ngModel]="p.precio" (change)="cambiarNumero('precio', $event)" /></div>
            <div><label>Anticipo</label>
              <input type="number" [ngModel]="p.anticipo" (change)="cambiarNumero('anticipo', $event)" /></div>
          </div>
          <p>Resta por cobrar: <strong>{{ p.precio - p.anticipo | currency: 'MXN' : 'symbol-narrow' }}</strong></p>
          <div><label>Fecha de entrega</label>
            <input type="date" [ngModel]="p.fecha_entrega" (change)="cambiarTexto('fecha_entrega', $event)" /></div>
          <div><label>Notas</label>
            <textarea rows="3" [ngModel]="p.notas" (change)="cambiarTexto('notas', $event)"></textarea></div>
          <p class="nota">{{ p.canal }} · {{ p.telefono || 'sin teléfono' }} · creado {{ p.creado | date: 'd MMM y, HH:mm' }}</p>
          <button class="peligro" (click)="borrar()">Borrar pedido</button>
        </div>
      </div>
    } @else if (error()) {
      <p class="error">{{ error() }}</p>
    }
  `,
  styles: `
    .titulo { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin: 12px 0; }
    .titulo h1 { margin: 0; }
    .rejilla { display: grid; grid-template-columns: 3fr 2fr; gap: 16px; align-items: start; }
    .previa { width: 100%; aspect-ratio: 3 / 2; object-fit: contain; border-radius: 8px; background: #111; }
    .acciones { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
    .verde { background: #25a35a; }
    .datos { display: grid; gap: 12px; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .nota { color: var(--suave); font-size: .85rem; margin: 8px 0 0; }
    p { margin: 0; }
    @media (max-width: 760px) { .rejilla { grid-template-columns: 1fr; } }
  `,
})
export class DetallePedido {
  servicio = inject(PedidosService);
  private router = inject(Router);

  id = input.required({ transform: numberAttribute });
  pedido = signal<Pedido | null>(null);
  ui = computed(() => lineaUI(this.pedido()?.linea ?? ''));
  generando = signal(false);
  error = signal('');
  version = signal(0);

  whatsapp = computed(() => {
    const p = this.pedido();
    const tel = p?.telefono.replace(/\D/g, '');
    if (!p || !tel) return null;
    const numero = tel.length === 10 ? `52${tel}` : tel;
    const texto = this.ui().mensaje(p);
    return `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`;
  });

  ngOnInit() {
    this.servicio.ver(this.id()).subscribe({
      next: (p) => this.pedido.set(p),
      error: () => this.error.set('No se encontró el pedido.'),
    });
  }

  cambiarConfig(config: Record<string, unknown>) {
    this.cambiar({ config });
  }

  cambiar(cambios: PedidoCambios) {
    this.servicio.actualizar(this.id(), cambios).subscribe({
      next: (p) => {
        this.pedido.set(p);
        this.version.update((v) => v + 1); // datos nuevos: refresca las vistas previas
      },
      error: () => this.error.set('No se pudo guardar el cambio.'),
    });
  }

  cambiarNumero(campo: keyof Pedido, ev: Event) {
    const valor = Number((ev.target as HTMLInputElement).value);
    if (!Number.isNaN(valor)) this.cambiar({ [campo]: valor });
  }

  cambiarTexto(campo: keyof Pedido, ev: Event) {
    const valor = (ev.target as HTMLInputElement).value;
    this.cambiar({ [campo]: valor || null } as PedidoCambios);
  }

  generar() {
    this.generando.set(true);
    this.error.set('');
    this.servicio.generar(this.id()).subscribe({
      next: (p) => {
        this.pedido.set(p);
        this.version.update((v) => v + 1);
        this.generando.set(false);
      },
      error: (e) => {
        this.generando.set(false);
        const detalle = e.error?.detail;
        this.error.set(typeof detalle === 'string' ? detalle : 'No se pudieron generar los archivos.');
      },
    });
  }

  borrar() {
    if (!confirm('¿Borrar este pedido y sus archivos?')) return;
    this.servicio.borrar(this.id()).subscribe(() => this.router.navigate(['/pedidos']));
  }
}
