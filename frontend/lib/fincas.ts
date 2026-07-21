/** Cliente tipado de /fincas y /especies-pasto. */

import { api } from "./api";

export interface Finca {
  id: string;
  nombre: string;
  estacion_clima_id: string | null;
}

export interface EspeciePasto {
  id: string;
  nombre: string;
  dias_descanso_ideal: number | null;
}

export const fincasApi = {
  listar: () => api.get<Finca[]>("/fincas/"),
  crear: (nombre: string) => api.post<Finca>("/fincas/", { nombre }),
};

export const especiesApi = {
  listar: () => api.get<EspeciePasto[]>("/especies-pasto"),
};
