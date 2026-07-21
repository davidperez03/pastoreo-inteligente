/** Cliente tipado de lotes y eventos de pastoreo (§9). */

import { api } from "./api";

export interface Lote {
  id: string;
  finca_id: string;
  nombre: string | null;
  n_animales: number;
  peso_promedio_kg: number;
  ua_equivalente: number;
  potrero_actual_id: string | null;
}

export interface EventoPastoreo {
  id: string;
  lote_id: string;
  potrero_id: string;
  fecha_entrada: string;
  fecha_salida: string | null;
  biomasa_inicial: number | null;
  biomasa_final: number | null;
}

export const ganadoApi = {
  listarLotes: (fincaId: string) => api.get<Lote[]>(`/fincas/${fincaId}/lotes`),

  crearLote: (datos: {
    finca_id: string;
    nombre: string;
    n_animales: number;
    peso_promedio_kg: number;
  }) => api.post<Lote>("/lotes/", datos),

  registrarEntrada: (datos: {
    lote_id: string;
    potrero_id: string;
    biomasa_inicial?: number;
  }) => api.post<EventoPastoreo>("/eventos/entrada", datos),

  registrarSalida: (datos: { lote_id: string; biomasa_final?: number }) =>
    api.post<EventoPastoreo>("/eventos/salida", datos),
};
