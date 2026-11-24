import { CUBO_UI } from './cubo/cubo';
import { GENERICA, LineaUI } from './lineas';
import { LETRERO_UI } from './letrero/letrero';
import { LITOFANO_UI } from './litofano/litofano';
import { LUNA_UI } from './luna/luna';
import { LUNA_PARED_UI } from './luna-pared/luna-pared';

/** Para agregar una línea nueva en pantalla: su LineaUI aquí y sus componentes en los @switch de pedidos/. */
const REGISTRO: Record<string, LineaUI> = {
  litofano: LITOFANO_UI,
  letrero: LETRERO_UI,
  luna: LUNA_UI,
  cubo: CUBO_UI,
  luna_pared: LUNA_PARED_UI,
};

export const lineaUI = (id: string): LineaUI => REGISTRO[id] ?? GENERICA;
