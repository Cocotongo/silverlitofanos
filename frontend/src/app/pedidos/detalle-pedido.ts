import { Component, computed, inject, input, numberAttribute, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ESTADOS, Encuadre, Estado, Pedido, PedidosService, textoEstado } from './pedidos.service';

@Component({
  selector: 'app-detalle-pedido',
  imports: [CurrencyPipe, DatePipe, FormsModule, RouterLink],
  template: `
    <a routerLink="/pedidos">← Pedidos</a>
    @if (pedido(); as p) {
      <div class="titulo">
        <h1>#{{ p.id }} · {{ p.cliente }}</h1>
        <span class="estado {{ p.estado }}">{{ texto(p.estado) }}</span>
      </div>

      <div class="rejilla">
        <div class="tarjeta">
          <div class="imagenes">
            <figure>
              <div class="marco-foto">
                <img class="original" [src]="servicio.urlFoto(p.id)" alt="Foto original"
                  (load)="medirFoto($event)" />
                @if (recorte(); as r) {
                  <div class="recorte" [style.left.%]="r.izq" [style.top.%]="r.arr"
                    [style.width.%]="r.ancho" [style.height.%]="r.alto"></div>
                }
              </div>
              <figcaption>Foto original (el recuadro es lo que se imprime)</figcaption>
            </figure>
            <figure>
              @if (p.stl_listo && !pendiente()) {
                <img [src]="servicio.urlPrevia(p.id, version())" alt="Vista previa encendida" />
                <figcaption>Así se verá encendido</figcaption>
              } @else {
                <img [src]="servicio.urlEnsayo(p.id, ensayo(), version())" alt="Prueba de encuadre" />
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

          <div class="acciones">
            <button (click)="generar()" [disabled]="generando()">
              {{ generando() ? 'Generando STL…' : p.stl_listo ? 'Volver a generar' : 'Generar STL' }}
            </button>
            @if (p.stl_listo) {
              <a class="boton" [href]="servicio.urlStl(p.id)">Descargar STL</a>
            }
            @if (whatsapp(); as w) {
              <a class="boton verde" [href]="w" target="_blank" rel="noopener">WhatsApp</a>
            }
          </div>
          @if (p.stl_listo) {
            <p class="nota">{{ p.medidas }} · ≈ {{ p.gramos }} g de {{ p.material.toUpperCase() }}</p>
          }
          @if (error()) { <p class="error">{{ error() }}</p> }
        </div>

        <div class="tarjeta datos">
          <div>
            <label>Estado</label>
            <select [ngModel]="p.estado" (ngModelChange)="cambiar({ estado: $event })">
              @for (e of estados; track e.valor) { <option [value]="e.valor">{{ e.texto }}</option> }
            </select>
          </div>
          <div class="doble">
            <div>
              <label>Forma</label>
              <select [ngModel]="p.forma" (ngModelChange)="cambiar({ forma: $event })">
                <option value="panel">Panel</option>
                <option value="cilindro">Cilindro</option>
              </select>
            </div>
            <div>
              <label>Material</label>
              <select [ngModel]="p.material" (ngModelChange)="cambiar({ material: $event })">
                <option value="petg">PETG</option>
                <option value="pla">PLA</option>
              </select>
            </div>
          </div>
          @if (p.forma === 'panel') {
            <div><label>Ancho (mm)</label>
              <input type="number" [ngModel]="p.ancho" (change)="cambiarNumero('ancho', $event)" /></div>
          } @else {
            <div class="doble">
              <div><label>Diámetro (mm)</label>
                <input type="number" [ngModel]="p.diametro" (change)="cambiarNumero('diametro', $event)" /></div>
              <div><label>Alto (mm)</label>
                <input type="number" [ngModel]="p.alto" (change)="cambiarNumero('alto', $event)" /></div>
            </div>
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
    .imagenes { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    figure { margin: 0; }
    figure img, .hueco { width: 100%; aspect-ratio: 3 / 2; object-fit: contain; border-radius: 8px; background: #111; }
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
    .hueco { display: grid; place-items: center; color: #888; }
    figcaption { font-size: .8rem; color: var(--suave); margin-top: 4px; text-align: center; }
    .acciones { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
    .verde { background: #25a35a; }
    .datos { display: grid; gap: 12px; }
    .doble { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .nota { color: var(--suave); font-size: .85rem; margin: 8px 0 0; }
    p { margin: 0; }
    @media (max-width: 760px) { .rejilla, .encuadre { grid-template-columns: 1fr; } }
  `,
})
export class DetallePedido {
  servicio = inject(PedidosService);
  private router = inject(Router);

  id = input.required({ transform: numberAttribute });
  estados = ESTADOS;
  pedido = signal<Pedido | null>(null);
  generando = signal(false);
  error = signal('');
  version = signal(0);

  // encuadre que se esta moviendo (ajuste) y el que se manda a la prueba rapida (ensayo)
  ajuste = signal<Encuadre>({ x: 0.5, y: 0.5, zoom: 1, mejorar: true });
  ensayo = signal<Encuadre>({ x: 0.5, y: 0.5, zoom: 1, mejorar: true });
  private tamFoto = signal<{ w: number; h: number } | null>(null);

  pendiente = computed(() => {
    const p = this.pedido();
    const a = this.ajuste();
    return !!p && (a.x !== p.encuadre_x || a.y !== p.encuadre_y || a.zoom !== p.zoom || a.mejorar !== p.mejorar);
  });

  // recuadro sobre la foto, en % (misma cuenta que encuadrar() en el backend)
  recorte = computed(() => {
    const p = this.pedido();
    const f = this.tamFoto();
    if (!p || !f) return null;
    const a = this.ajuste();
    const r = p.forma === 'panel' ? f.w / f.h : (Math.PI * p.diametro) / p.alto;
    let [cw, ch] = f.w / f.h > r ? [f.h * r, f.h] : [f.w, f.w / r];
    cw /= a.zoom;
    ch /= a.zoom;
    const izq = Math.min(Math.max(a.x * f.w - cw / 2, 0), f.w - cw);
    const arr = Math.min(Math.max(a.y * f.h - ch / 2, 0), f.h - ch);
    return { izq: (izq / f.w) * 100, arr: (arr / f.h) * 100, ancho: (cw / f.w) * 100, alto: (ch / f.h) * 100 };
  });

  whatsapp = computed(() => {
    const p = this.pedido();
    const tel = p?.telefono.replace(/\D/g, '');
    if (!p || !tel) return null;
    const numero = tel.length === 10 ? `52${tel}` : tel;
    const texto = `Hola ${p.cliente}, te comparto la vista previa de tu lámpara (pedido #${p.id}).`;
    return `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`;
  });

  ngOnInit() {
    this.servicio.ver(this.id()).subscribe({
      next: (p) => {
        this.pedido.set(p);
        this.deshacerEncuadre();
      },
      error: () => this.error.set('No se encontró el pedido.'),
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
    this.cambiar({ encuadre_x: a.x, encuadre_y: a.y, zoom: a.zoom, mejorar: a.mejorar });
  }

  deshacerEncuadre() {
    const p = this.pedido();
    if (!p) return;
    this.ajuste.set({ x: p.encuadre_x, y: p.encuadre_y, zoom: p.zoom, mejorar: p.mejorar });
    this.probar();
  }

  texto = (e: Estado) => textoEstado(e);

  cambiar(cambios: Partial<Pedido>) {
    this.servicio.actualizar(this.id(), cambios).subscribe({
      next: (p) => {
        this.pedido.set(p);
        this.version.update((v) => v + 1); // forma o medidas nuevas: refresca la prueba rapida
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
    this.cambiar({ [campo]: valor || null } as Partial<Pedido>);
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
      error: () => {
        this.generando.set(false);
        this.error.set('No se pudo generar el STL.');
      },
    });
  }

  borrar() {
    if (!confirm('¿Borrar este pedido y sus archivos?')) return;
    this.servicio.borrar(this.id()).subscribe(() => this.router.navigate(['/pedidos']));
  }
}
