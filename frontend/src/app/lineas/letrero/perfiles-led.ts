import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { CAMPOS_PERFIL, LetreroService, PerfilLed } from './letrero.service';

/** Pantalla para ver y editar los perfiles de construcción de letreros (uno por tira/proveedor). */
@Component({
  selector: 'app-perfiles-led',
  imports: [FormsModule],
  template: `
    <h1>Perfiles de letreros LED</h1>
    <p class="nota">Cada perfil guarda las medidas para una tira o proveedor. Al generar un letrero se usan las del perfil
      elegido, y quedan anotadas en el pedido.</p>

    <div class="pestanas">
      @for (p of perfiles(); track p.id) {
        <button [class.secundario]="p.id !== actual()?.id" (click)="elegir(p)">{{ p.nombre }}</button>
      }
      <button class="secundario" (click)="nuevo()">+ Nuevo perfil</button>
    </div>

    @if (actual(); as p) {
      <form class="tarjeta" (ngSubmit)="guardar()">
        <div class="doble">
          <div><label>Nombre</label><input name="nombre" [(ngModel)]="p.nombre" required /></div>
          <div><label>Proveedor</label><input name="proveedor" [(ngModel)]="p.proveedor" /></div>
        </div>
        @for (g of grupos; track g.grupo) {
          <h3>{{ g.grupo }}</h3>
          <div class="rejilla">
            @for (c of g.campos; track c.id) {
              <div>
                <label>{{ c.texto }} (mm)</label>
                <input type="number" step="0.1" min="0" [name]="c.id" [(ngModel)]="$any(p)[c.id]" required />
              </div>
            }
          </div>
        }
        @if (mensaje()) { <p [class.error]="esError()" class="nota">{{ mensaje() }}</p> }
        <div class="acciones">
          <button type="submit">{{ p.id ? 'Guardar cambios' : 'Crear perfil' }}</button>
          @if (p.id && perfiles().length > 1) {
            <button type="button" class="peligro" (click)="borrar(p)">Borrar perfil</button>
          }
        </div>
      </form>
    }
  `,
  styles: `
    .nota { color: var(--suave); font-size: .9rem; }
    .pestanas { display: flex; gap: 6px; flex-wrap: wrap; margin: 14px 0; }
    .pestanas button { padding: 6px 10px; font-size: .85rem; }
    form { display: grid; gap: 12px; }
    h3 { margin: 8px 0 0; font-size: 1rem; }
    .rejilla { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .acciones { display: flex; gap: 8px; }
    @media (max-width: 560px) { .doble { grid-template-columns: 1fr; } }
  `,
})
export class PerfilesLed {
  private servicio = inject(LetreroService);
  grupos = CAMPOS_PERFIL;
  perfiles = signal<PerfilLed[]>([]);
  actual = signal<PerfilLed | null>(null);
  mensaje = signal('');
  esError = signal(false);

  constructor() {
    this.cargar();
  }

  private cargar(elegir?: number, aviso = '') {
    this.servicio.perfiles().subscribe((l) => {
      this.perfiles.set(l);
      const p = l.find((x) => x.id === elegir) ?? l[0];
      if (p) this.elegir(p);
      if (aviso) this.avisar(aviso, false);
    });
  }

  elegir(p: PerfilLed) {
    this.actual.set({ ...p });
    this.mensaje.set('');
  }

  nuevo() {
    const base = this.perfiles()[0];
    this.actual.set({ ...base, id: 0, nombre: 'Nuevo perfil', proveedor: '' });
    this.mensaje.set('Se copiaron las medidas del primer perfil; cámbialas y crea el perfil.');
    this.esError.set(false);
  }

  guardar() {
    const p = this.actual();
    if (!p) return;
    const { id, ...datos } = p;
    const peticion = id ? this.servicio.editarPerfil(id, datos) : this.servicio.crearPerfil(datos);
    peticion.subscribe({
      next: (r) => this.cargar(r.id, 'Guardado.'),
      error: (e) => this.avisar(typeof e.error?.detail === 'string' ? e.error.detail : 'Revisa las medidas: hay valores no válidos.', true),
    });
  }

  borrar(p: PerfilLed) {
    if (!confirm(`¿Borrar el perfil «${p.nombre}»?`)) return;
    this.servicio.borrarPerfil(p.id).subscribe(() => this.cargar());
  }

  private avisar(texto: string, error: boolean) {
    this.mensaje.set(texto);
    this.esError.set(error);
  }
}
