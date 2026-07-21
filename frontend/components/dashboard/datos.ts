/** Capa de datos del dashboard con fallback a mocks.
 *
 * Cada función intenta primero la API real (via lib/api). Si falla —
 * ApiError del backend o error de red — devuelve mocks tipados realistas
 * marcados con esMock=true, que la UI presenta como "datos de demostración".
 * Así el dashboard funciona antes y después de la integración con el backend.
 */

import { api } from "@/lib/api";
import type {
  LoteResumen,
  PotreroResumen,
  PuntoHistorial,
  ResultadoDatos,
  SugerenciaRotacion,
} from "./tipos";

/** Finca por defecto mientras no exista selector de finca en la UI. */
export const FINCA_DEMO_ID = "finca-demo";

async function conFallback<T>(
  peticion: () => Promise<T>,
  mock: () => T,
): Promise<ResultadoDatos<T>> {
  try {
    return { datos: await peticion(), esMock: false };
  } catch {
    // ApiError (respuesta no-2xx) o TypeError (red caída): en ambos casos
    // el dashboard debe seguir siendo útil con datos de demostración.
    return { datos: mock(), esMock: true };
  }
}

// ---------------------------------------------------------------------------
// Mocks deterministas (sin Math.random: mismas cifras en cada render)
// ---------------------------------------------------------------------------

/** PRNG determinista (mulberry32) para series sintéticas reproducibles. */
function crearRng(semilla: number): () => number {
  let s = semilla >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function semillaDesdeTexto(texto: string): number {
  let h = 2166136261;
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function fechaIso(base: Date, desplazamientoDias: number): string {
  const d = new Date(base);
  d.setDate(d.getDate() + desplazamientoDias);
  return d.toISOString().slice(0, 10);
}

const POTREROS_MOCK: PotreroResumen[] = [
  {
    id: "pot-la-ceiba",
    nombre: "La Ceiba",
    area_ha: 12.5,
    estado: "ocupado",
    biomasa_kg_ms_ha: 1450,
    factor_fatiga: 1.0,
    dias_en_estado: 4,
  },
  {
    id: "pot-el-saman",
    nombre: "El Samán",
    area_ha: 9.8,
    estado: "descanso",
    biomasa_kg_ms_ha: 1980,
    factor_fatiga: 0.92,
    dias_en_estado: 12,
  },
  {
    id: "pot-mata-de-monte",
    nombre: "Mata de Monte",
    area_ha: 15.2,
    estado: "listo",
    biomasa_kg_ms_ha: 3120,
    factor_fatiga: 1.0,
    dias_en_estado: 28,
  },
  {
    id: "pot-cano-seco",
    nombre: "Caño Seco",
    area_ha: 7.4,
    estado: "descanso",
    biomasa_kg_ms_ha: 1210,
    factor_fatiga: 0.78,
    dias_en_estado: 6,
  },
  {
    id: "pot-la-esperanza",
    nombre: "La Esperanza",
    area_ha: 11.0,
    estado: "listo",
    biomasa_kg_ms_ha: 2860,
    factor_fatiga: 0.95,
    dias_en_estado: 24,
  },
  {
    id: "pot-palo-alto",
    nombre: "Palo Alto",
    area_ha: 8.6,
    estado: "ocupado",
    biomasa_kg_ms_ha: 890,
    factor_fatiga: 0.85,
    dias_en_estado: 7,
  },
];

const LOTES_MOCK: LoteResumen[] = [
  {
    id: "lote-ceba-1",
    nombre: "Lote Ceba 1",
    n_animales: 42,
    ua_equivalente: 38.5,
    potrero_actual_id: "pot-la-ceiba",
  },
  {
    id: "lote-cria",
    nombre: "Lote Cría",
    n_animales: 35,
    ua_equivalente: 41.2,
    potrero_actual_id: "pot-palo-alto",
  },
];

function sugerenciasMock(): SugerenciaRotacion[] {
  const hoy = new Date();
  return [
    { lote_id: "lote-ceba-1", potrero_id: "pot-mata-de-monte", fecha: fechaIso(hoy, 2) },
    { lote_id: "lote-cria", potrero_id: "pot-la-esperanza", fecha: fechaIso(hoy, 5) },
  ];
}

/** 90 días de historial sintético: crecimiento en descanso, caída durante
 * ocupación, NDVI cada ~5 días con ruido, y eventos entrada/salida en los
 * cambios de ciclo. Determinista por id de potrero. */
function historialMock(potreroId: string): PuntoHistorial[] {
  const rng = crearRng(semillaDesdeTexto(potreroId));
  const hoy = new Date();
  const diasDescanso = 26 + Math.floor(rng() * 8);
  const diasOcupado = 5 + Math.floor(rng() * 4);
  const ciclo = diasDescanso + diasOcupado;
  const desfase = Math.floor(rng() * ciclo);
  let biomasa = 1400 + rng() * 900;

  const puntos: PuntoHistorial[] = [];
  for (let dia = 0; dia < 90; dia++) {
    const diaCiclo = (dia + desfase) % ciclo;
    const ocupado = diaCiclo >= diasDescanso;
    let evento: PuntoHistorial["evento"] = null;
    if (dia > 0 && diaCiclo === diasDescanso) evento = "entrada";
    if (dia > 0 && diaCiclo === 0) evento = "salida";

    biomasa += ocupado ? -(130 + rng() * 70) : 45 + rng() * 40;
    biomasa = Math.min(3500, Math.max(800, biomasa));

    const hayNdvi = dia % 5 === 2;
    puntos.push({
      fecha: fechaIso(hoy, dia - 89),
      biomasa_modelo: Math.round(biomasa),
      biomasa_ndvi: hayNdvi
        ? Math.round(Math.min(3500, Math.max(800, biomasa * (0.85 + rng() * 0.3))))
        : null,
      evento,
    });
  }
  return puntos;
}

// ---------------------------------------------------------------------------
// API pública de la capa de datos
// ---------------------------------------------------------------------------

export function obtenerPotreros(
  fincaId: string = FINCA_DEMO_ID,
): Promise<ResultadoDatos<PotreroResumen[]>> {
  return conFallback(
    () => api.get<PotreroResumen[]>(`/fincas/${fincaId}/potreros`),
    () => POTREROS_MOCK,
  );
}

export function obtenerLotes(
  fincaId: string = FINCA_DEMO_ID,
): Promise<ResultadoDatos<LoteResumen[]>> {
  return conFallback(
    () => api.get<LoteResumen[]>(`/fincas/${fincaId}/lotes`),
    () => LOTES_MOCK,
  );
}

export function obtenerHistorial(
  potreroId: string,
): Promise<ResultadoDatos<PuntoHistorial[]>> {
  return conFallback(
    () => api.get<PuntoHistorial[]>(`/potreros/${potreroId}/historial`),
    () => historialMock(potreroId),
  );
}

export function obtenerSugerencias(
  fincaId: string = FINCA_DEMO_ID,
): Promise<ResultadoDatos<SugerenciaRotacion[]>> {
  return conFallback(
    () => api.get<SugerenciaRotacion[]>(`/fincas/${fincaId}/rotacion/sugerir`),
    sugerenciasMock,
  );
}
