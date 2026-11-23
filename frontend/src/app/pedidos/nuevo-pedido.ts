import { Component, computed, effect, inject, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { LetreroNuevo } from '../lineas/letrero/letrero';
import { LitofanoNuevo } from '../lineas/litofano/litofano';
import { LunaNuevo } from '../lineas/luna/luna';
import { PedidosService } from './pedidos.service';

@Component({
  selector: 'app-nuevo-pedido',
  imports: [ReactiveFormsModule, CurrencyPipe, LitofanoNuevo, LetreroNuevo, LunaNuevo],
  template: `
    <h1>Nuevo pedido</h1>
    <form class="tarjeta rejilla" [formGroup]="form" (ngSubmit)="guardar()">
      @if (linea()?.archivo; as a) {
        <div class="foto">
          <label>{{ a.etiqueta }}</label>
          <label class="zona" [class.con-foto]="vista() || archivo">
            @if (vista()) {
              <img [src]="vista()" alt="Archivo elegido" />
            } @else if (archivo) {
              <span>{{ archivo.name }}</span>
            } @else {
              <span>Toca para elegir el archivo</span>
            }
            <input type="file" [accept]="a.acepta" (change)="elegirArchivo($event)" hidden />
          </label>
        </div>
      } @else {
        @switch (linea()?.id) {
          @case ('letrero') { <app-letrero-nuevo [base]="$any(producto()?.config)" (config)="config.set($event)" /> }
          @case ('luna') { <app-luna-nuevo [base]="$any(producto()?.config)" (config)="config.set($event)" /> }
        }
      }

      <div class="campos">
        <div><label>Cliente</label><input formControlName="cliente" placeholder="Nombre" /></div>
        <div><label>Teléfono / WhatsApp</label><input formControlName="telefono" placeholder="81 1234 5678" /></div>
        <div>
          <label>Canal</label>
          <select formControlName="canal">
            @for (c of canales; track c) { <option>{{ c }}</option> }
          </select>
        </div>
        <div>
          <label>Producto</label>
          <select formControlName="producto" (change)="cambiarProducto()">
            @for (l of servicio.lineas(); track l.id) {
              <optgroup [label]="l.nombre">
                @for (p of l.productos; track p.id) {
                  <option [value]="l.id + '/' + p.id">{{ p.nombre }} · {{ p.precio | currency: 'MXN' : 'symbol-narrow' : '1.0-0' }}</option>
                }
              </optgroup>
            }
          </select>
        </div>
        @switch (linea()?.id) {
          @case ('litofano') { <app-litofano-nuevo (config)="config.set($event)" /> }
        }
        <div class="doble">
          <div><label>Precio</label><input type="number" formControlName="precio" /></div>
          <div><label>Anticipo</label><input type="number" formControlName="anticipo" /></div>
        </div>
        <div><label>Fecha de entrega</label><input type="date" formControlName="fecha_entrega" /></div>
        <div><label>Notas</label><textarea rows="2" formControlName="notas" placeholder="Texto, fecha, base RGB…"></textarea></div>
        @if (error()) { <p class="error">{{ error() }}</p> }
        <button type="submit" [disabled]="form.invalid || faltaArchivo() || guardando()">
          {{ guardando() ? 'Guardando…' : 'Guardar pedido' }}
        </button>
      </div>
    </form>
  `,
  styles: `
    .rejilla { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .campos { display: grid; gap: 12px; align-content: start; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .zona { display: grid; place-items: center; min-height: 260px; border: 2px dashed var(--borde);
      border-radius: 10px; cursor: pointer; color: var(--suave); overflow: hidden; margin: 0; }
    .zona.con-foto { border-style: solid; }
    .zona img { width: 100%; height: 100%; object-fit: contain; filter: grayscale(1); }
    @media (max-width: 700px) { .rejilla { grid-template-columns: 1fr; } }
  `,
})
export class NuevoPedido {
  servicio = inject(PedidosService);
  private router = inject(Router);
  private fb = inject(FormBuilder);

  canales = ['WhatsApp', 'Facebook', 'Instagram', 'Mercado Libre', 'Bazar', 'Otro'];
  config = signal<Record<string, unknown>>({});
  vista = signal<string | null>(null);
  guardando = signal(false);
  error = signal('');
  archivo: File | null = null;

  form = this.fb.nonNullable.group({
    cliente: ['', Validators.required],
    telefono: [''],
    canal: ['WhatsApp'],
    producto: ['litofano/panel-150'],
    precio: [0, [Validators.required, Validators.min(0)]],
    anticipo: [0, Validators.min(0)],
    fecha_entrega: [''],
    notas: [''],
  });

  // el valor del producto es "linea/producto"
  private eleccion = signal(this.form.controls.producto.value);
  linea = computed(() => this.servicio.linea(this.eleccion().split('/')[0]));
  producto = computed(() => this.linea()?.productos.find((p) => p.id === this.eleccion().split('/')[1]));
  private archivoElegido = signal(false);
  faltaArchivo = computed(() => !!this.linea()?.archivo?.requerido && !this.archivoElegido());

  constructor() {
    // cuando llega el catalogo, pone el precio del producto elegido
    effect(() => {
      if (this.servicio.lineas().length) this.cambiarProducto();
    });
  }

  cambiarProducto() {
    const valor = this.form.controls.producto.value;
    const [linea, id] = valor.split('/');
    if (linea !== this.linea()?.id) {
      this.config.set({});
      this.quitarArchivo();
    }
    this.eleccion.set(valor);
    const p = this.servicio.linea(linea)?.productos.find((x) => x.id === id);
    if (p) this.form.controls.precio.setValue(p.precio);
  }

  elegirArchivo(ev: Event) {
    const archivo = (ev.target as HTMLInputElement).files?.[0];
    if (!archivo) return;
    this.quitarArchivo();
    this.archivo = archivo;
    this.archivoElegido.set(true);
    if (archivo.type.startsWith('image/')) this.vista.set(URL.createObjectURL(archivo));
  }

  private quitarArchivo() {
    const vistaAnterior = this.vista();
    if (vistaAnterior) URL.revokeObjectURL(vistaAnterior);
    this.vista.set(null);
    this.archivo = null;
    this.archivoElegido.set(false);
  }

  guardar() {
    if (this.faltaArchivo()) return;
    const { producto, ...resto } = this.form.getRawValue();
    const [linea, id] = producto.split('/');
    const datos = new FormData();
    for (const [k, v] of Object.entries(resto)) {
      if (v !== '' && v !== null) datos.append(k, String(v));
    }
    datos.append('linea', linea);
    datos.append('producto', id);
    datos.append('config', JSON.stringify(this.config()));
    if (this.archivo) datos.append('archivo', this.archivo);
    this.guardando.set(true);
    this.servicio.crear(datos).subscribe({
      next: (p) => this.router.navigate(['/pedidos', p.id]),
      error: (e) => {
        this.guardando.set(false);
        this.error.set(e.error?.detail ?? 'No se pudo guardar el pedido.');
      },
    });
  }
}
