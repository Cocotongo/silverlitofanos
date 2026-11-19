import { GENERICA, LineaUI } from './lineas';
import { LITOFANO_UI } from './litofano/litofano';

/** Para agregar una línea nueva en pantalla: su LineaUI aquí y sus componentes en los @switch de pedidos/. */
const REGISTRO: Record<string, LineaUI> = {
  litofano: LITOFANO_UI,
};

export const lineaUI = (id: string): LineaUI => REGISTRO[id] ?? GENERICA;
