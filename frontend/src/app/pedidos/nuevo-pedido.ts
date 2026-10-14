import { Component, inject, signal } from '@angular/core';
import { CurrencyPipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { PedidosService, Producto } from './pedidos.service';

@Component({
  selector: 'app-nuevo-pedido',
  imports: [ReactiveFormsModule, CurrencyPipe],
  template: `
    <h1>Nuevo pedido</h1>
    <form class="tarjeta rejilla" [formGroup]="form" (ngSubmit)="guardar()">
      <div class="foto">
        <label>Foto del cliente</label>
        <label class="zona" [class.con-foto]="vista()">
          @if (vista()) {
            <img [src]="vista()" alt="Foto elegida" />
          } @else {
            <span>Toca para elegir una foto</span>
          }
          <input type="file" accept="image/*" (change)="elegirFoto($event)" hidden />
        </label>
      </div>

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
            @for (p of productos(); track p.id) {
              <option [value]="p.id">{{ p.nombre }} · {{ p.precio | currency: 'MXN' : 'symbol-narrow' : '1.0-0' }}</option>
            }
          </select>
        </div>
        <div>
          <label>Material</label>
          <select formControlName="material">
            <option value="petg">PETG blanco</option>
            <option value="pla">PLA blanco</option>
          </select>
        </div>
        <div class="doble">
          <div><label>Precio</label><input type="number" formControlName="precio" /></div>
          <div><label>Anticipo</label><input type="number" formControlName="anticipo" /></div>
        </div>
        <div><label>Fecha de entrega</label><input type="date" formControlName="fecha_entrega" /></div>
        <div><label>Notas</label><textarea rows="2" formControlName="notas" placeholder="Texto, fecha, base RGB…"></textarea></div>
        @if (error()) { <p class="error">{{ error() }}</p> }
        <button type="submit" [disabled]="form.invalid || !archivo || guardando()">
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
  private servicio = inject(PedidosService);
  private router = inject(Router);
  private fb = inject(FormBuilder);

  canales = ['WhatsApp', 'Facebook', 'Instagram', 'Mercado Libre', 'Bazar', 'Otro'];
  productos = signal<Producto[]>([]);
  vista = signal<string | null>(null);
  guardando = signal(false);
  error = signal('');
  archivo: File | null = null;

  form = this.fb.nonNullable.group({
    cliente: ['', Validators.required],
    telefono: [''],
    canal: ['WhatsApp'],
    producto: ['panel-150'],
    material: ['petg'],
    precio: [0, [Validators.required, Validators.min(0)]],
    anticipo: [0, Validators.min(0)],
    fecha_entrega: [''],
    notas: [''],
  });

  constructor() {
    this.servicio.productos().subscribe((l) => {
      this.productos.set(l);
      this.cambiarProducto();
    });
  }

  cambiarProducto() {
    const p = this.productos().find((x) => x.id === this.form.controls.producto.value);
    if (p) this.form.controls.precio.setValue(p.precio);
  }

  elegirFoto(ev: Event) {
    const archivo = (ev.target as HTMLInputElement).files?.[0];
    if (!archivo) return;
    this.archivo = archivo;
    const vistaAnterior = this.vista();
    if (vistaAnterior) URL.revokeObjectURL(vistaAnterior);
    this.vista.set(URL.createObjectURL(archivo));
  }

  guardar() {
    if (!this.archivo) return;
    const datos = new FormData();
    for (const [k, v] of Object.entries(this.form.getRawValue())) {
      if (v !== '' && v !== null) datos.append(k, String(v));
    }
    datos.append('foto', this.archivo);
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
