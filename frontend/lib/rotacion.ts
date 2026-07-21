/** Cliente tipado de /rotacion/sugerir (§7). */

import { api } from "./api";

export interface Movimiento {
  lote_id: string;
  potrero_id: string;
  fecha: string;
}

interface RotacionResponse {
  finca_id: string;
  horizonte_dias: number;
  movimientos: Movimiento[];
  advertencias: string[];
}

export const rotacionApi = {
  sugerir: (fincaId: string, horizonteDias = 14) =>
    api.get<RotacionResponse>(
      `/fincas/${fincaId}/rotacion/sugerir?horizonte_dias=${horizonteDias}`,
    ),
};
