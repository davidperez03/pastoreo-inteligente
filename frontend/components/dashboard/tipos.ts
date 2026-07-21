/** Tipos del dominio para la UI del dashboard (Unidad 10).
 *
 * Reflejan los contratos de los endpoints de §9 de la especificación:
 * - GET /fincas/{finca_id}/potreros        -> PotreroResumen[]
 * - GET /fincas/{finca_id}/lotes           -> LoteResumen[]
 * - GET /potreros/{id}/historial           -> PuntoHistorial[]
 * - GET /fincas/{finca_id}/rotacion/sugerir -> SugerenciaRotacion[]
 */

export type EstadoPotrero = "descanso" | "ocupado" | "listo";

export interface PotreroResumen {
  id: string;
  nombre: string;
  area_ha: number;
  estado: EstadoPotrero;
  /** Biomasa disponible estimada (kg MS/ha); null si aún no hay cálculo. */
  biomasa_kg_ms_ha: number | null;
  /** Factor de fatiga (memoria de sobrepastoreo, §16); 1.0 = sin castigo. */
  factor_fatiga: number;
  dias_en_estado: number | null;
}

export interface LoteResumen {
  id: string;
  nombre: string;
  n_animales: number;
  ua_equivalente: number;
  potrero_actual_id: string | null;
}

export type EventoHistorial = "entrada" | "salida";

/** Punto de la serie temporal del historial (§9): biomasa del modelo
 * agronómico vs. lectura NDVI satelital vs. eventos reales de manejo. */
export interface PuntoHistorial {
  /** Fecha ISO (YYYY-MM-DD). */
  fecha: string;
  biomasa_modelo: number | null;
  biomasa_ndvi: number | null;
  evento: EventoHistorial | null;
}

export interface SugerenciaRotacion {
  lote_id: string;
  potrero_id: string;
  /** Fecha ISO sugerida para el movimiento. */
  fecha: string;
}

/** Resultado de la capa de datos: payload + procedencia.
 * esMock=true significa que la API no respondió y se sirven datos de
 * demostración — la UI lo muestra como banda informativa. */
export interface ResultadoDatos<T> {
  datos: T;
  esMock: boolean;
}
