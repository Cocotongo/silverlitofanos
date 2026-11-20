import { Routes } from '@angular/router';

import { ListaPedidos } from './pedidos/lista-pedidos';
import { NuevoPedido } from './pedidos/nuevo-pedido';
import { DetallePedido } from './pedidos/detalle-pedido';
import { PerfilesLed } from './lineas/letrero/perfiles-led';

export const routes: Routes = [
  { path: '', redirectTo: 'pedidos', pathMatch: 'full' },
  { path: 'pedidos', component: ListaPedidos, title: 'Pedidos' },
  { path: 'pedidos/nuevo', component: NuevoPedido, title: 'Nuevo pedido' },
  { path: 'pedidos/:id', component: DetallePedido, title: 'Pedido' },
  { path: 'letreros/perfiles', component: PerfilesLed, title: 'Perfiles de letreros' },
];
