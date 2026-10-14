import { Component, computed, inject, signal } from '@angular/core';
import { CurrencyPipe, DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ESTADOS, Estado, Pedido, PedidosService, textoEstado } from './pedidos.service';

@Component({
  selector: 'app-lista-pedidos',
  imports: [RouterLink, CurrencyPipe, DatePipe],
  template: `
    <h1>Pedidos</h1>

    <div class="resumen">
      <div class="tarjeta"><small>Activos</small><strong>{{ activos() }}</strong></div>
      <div class="tarjeta"><small>Por cobrar</small><strong>{{ porCobrar() | currency: 'MXN' : 'symbol-narrow' }}</strong></div>
      <div class="tarjeta"><small>Vendido</small><strong>{{ vendido() | currency: 'MXN' : 'symbol-narrow' }}</strong></div>
    </div>

    <div class="filtros">
      <button [class.secundario]="filtro() !== ''" (click)="filtrar('')">Todos</button>
      @for (e of estados; track e.valor) {
        <button [class.secundario]="filtro() !== e.valor" (click)="filtrar(e.valor)">{{ e.texto }}</button>
      }
    </div>

    @if (error()) { <p class="error">{{ error() }}</p> }

    <div class="lista">
      @for (p of pedidos(); track p.id) {
        <a class="tarjeta fila" [routerLink]="['/pedidos', p.id]">
          <img [src]="foto(p.id)" alt="" loading="lazy" />
          <div class="info">
            <strong>#{{ p.id }} · {{ p.cliente }}</strong>
            <small>{{ p.forma === 'panel' ? 'Panel' : 'Cilindro' }} · {{ p.material.toUpperCase() }} · {{ p.canal }}</small>
            <small>
              Creado {{ p.creado | date: 'd MMM' }}
              @if (p.fecha_entrega) { · Entrega {{ p.fecha_entrega | date: 'd MMM' }} }
            </small>
          </div>
          <div class="derecha">
            <span class="estado {{ p.estado }}">{{ texto(p.estado) }}</span>
            <span>{{ p.precio | currency: 'MXN' : 'symbol-narrow' }}</span>
          </div>
        </a>
      } @empty {
        <div class="tarjeta vacio">
          No hay pedidos{{ filtro() ? ' en este estado' : '' }}. <a routerLink="/pedidos/nuevo">Crea el primero</a>.
        </div>
      }
    </div>
  `,
  styles: `
    .resumen { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
    .resumen small { display: block; color: var(--suave); }
    .resumen strong { font-size: 1.3rem; }
    .filtros { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
    .filtros button { padding: 6px 10px; font-size: .85rem; }
    .lista { display: grid; gap: 8px; }
    .fila { display: flex; gap: 12px; align-items: center; color: inherit; text-decoration: none; padding: 10px; }
    .fila:hover { border-color: var(--acento); }
    .fila img { width: 64px; height: 48px; object-fit: cover; border-radius: 6px; filter: grayscale(1); }
    .info { flex: 1; display: grid; gap: 2px; min-width: 0; }
    .info small { color: var(--suave); }
    .derecha { display: grid; justify-items: end; gap: 4px; }
    .vacio { text-align: center; color: var(--suave); }
    @media (max-width: 560px) { .resumen strong { font-size: 1rem; } .fila img { display: none; } }
  `,
})
export class ListaPedidos {
  private servicio = inject(PedidosService);

  estados = ESTADOS;
  pedidos = signal<Pedido[]>([]);
  filtro = signal<Estado | ''>('');
  error = signal('');
  private todos = signal<Pedido[]>([]);

  activos = computed(
    () => this.todos().filter((p) => !['entregado', 'cancelado'].includes(p.estado)).length,
  );
  porCobrar = computed(() =>
    this.todos()
      .filter((p) => p.estado !== 'cancelado' && p.estado !== 'entregado')
      .reduce((s, p) => s + (p.precio - p.anticipo), 0),
  );
  vendido = computed(() =>
    this.todos().filter((p) => p.estado === 'entregado').reduce((s, p) => s + p.precio, 0),
  );

  constructor() {
    this.servicio.listar().subscribe({
      next: (l) => {
        this.todos.set(l);
        this.pedidos.set(l);
      },
      error: () => this.error.set('No se pudo conectar con el servidor. ¿Está corriendo el backend?'),
    });
  }

  filtrar(e: Estado | '') {
    this.filtro.set(e);
    this.pedidos.set(e ? this.todos().filter((p) => p.estado === e) : this.todos());
  }

  texto = textoEstado;
  foto = (id: number) => this.servicio.urlFoto(id);
}
