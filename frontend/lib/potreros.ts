/** Cliente tipado de /potreros (forma real de PotreroResponse en el backend). */

import { api } from "./api";

export interface PotreroApi {
  id: string;
  finca_id: string;
  nombre: string;
  area_ha: number;
  estado: "descanso" | "ocupado" | "listo";
  especie_pasto_id: string;
  tipo_suelo: string | null;
  fuente_agua: boolean;
  factor_fatiga: number;
  metodo_levantamiento: string;
  accuracy_m: number | null;
  biomasa_actual_kg_ms_ha: number | null;
  fecha_ultima_salida: string | null;
  geojson: { type: "Polygon"; coordinates: number[][][] };
  advertencia: string | null;
}

export interface CuerpoCrearPotrero {
  finca_id: string;
  nombre: string;
  puntos: [number, number][];
  especie_pasto_id: string;
  tipo_suelo: string;
  metodo_levantamiento: string;
  accuracy_m: number;
}

export const potrerosApi = {
  listar: (fincaId: string) => api.get<PotreroApi[]>(`/fincas/${fincaId}/potreros`),
  crear: (cuerpo: CuerpoCrearPotrero) => api.post<PotreroApi>("/potreros/", cuerpo),
};
