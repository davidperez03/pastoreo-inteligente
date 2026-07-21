/** Tipos y constantes compartidas de la unidad de mapa/planimetría (§3 del SRP). */

/** Punto [lat, lng] en WGS84 — mismo orden que el contrato del backend (§3.2). */
export type PuntoLatLng = [number, number];

/** Respuesta del backend al crear un potrero (contrato de §3.3). */
export interface RespuestaPotrero {
  id?: string;
  area_ha?: number;
  n_puntos?: number;
  advertencia?: string | null;
}

/** Cuerpo del POST /potreros/ (§5 del SRP). */
export interface CuerpoCrearPotrero {
  finca_id: string;
  nombre: string;
  puntos: PuntoLatLng[];
  especie_pasto_id: string;
  tipo_suelo: TipoSuelo;
  metodo_levantamiento: MetodoLevantamiento;
  accuracy_m: number;
}

export interface EspeciePasto {
  id: string;
  nombre: string;
}

// Seeds hardcodeadas temporalmente: en la integración con el backend estas
// especies (y sus ids reales) vendrán de la API (GET /especies-pasto/).
export const ESPECIES_PASTO: readonly EspeciePasto[] = [
  { id: "brachiaria-decumbens", nombre: "Brachiaria decumbens" },
  { id: "brachiaria-brizantha-marandu", nombre: "Brachiaria brizantha (Marandú)" },
  { id: "panicum-maximum-mombasa", nombre: "Panicum maximum (Mombasa)" },
  { id: "cynodon-nlemfuensis-estrella", nombre: "Cynodon nlemfuensis (Estrella)" },
  { id: "sabana-nativa-trachypogon", nombre: "Sabana nativa (Trachypogon)" },
] as const;

export const TIPOS_SUELO = ["franco", "arcilloso", "arenoso"] as const;
export type TipoSuelo = (typeof TIPOS_SUELO)[number];

export const METODOS_LEVANTAMIENTO = [
  { valor: "gps_celular", etiqueta: "GPS de celular" },
  { valor: "rtk", etiqueta: "GPS diferencial / RTK" },
  { valor: "dron", etiqueta: "Fotogrametría con dron" },
  { valor: "digitalizacion", etiqueta: "Digitalización sobre satélite" },
  { valor: "manual", etiqueta: "Manual" },
] as const;
export type MetodoLevantamiento = (typeof METODOS_LEVANTAMIENTO)[number]["valor"];

/** Centro por defecto del mapa: Casanare, Colombia. */
export const CENTRO_CASANARE: PuntoLatLng = [5.337, -72.396];
export const ZOOM_INICIAL = 15;
