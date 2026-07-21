"use client";

/** Área del polígono en curso, calculada localmente con Turf (§13 del SRP:
 * retroalimentación inmediata en el cliente, sin esperar al backend). */

import * as turf from "@turf/turf";
import type { PuntoLatLng } from "./tipos";
import styles from "./mapa.module.css";

/** Área geodésica en hectáreas del anillo [lat,lng][] (Turf usa [lng,lat]). */
export function areaHectareas(puntos: PuntoLatLng[]): number | null {
  if (puntos.length < 3) {
    return null;
  }
  const anillo: [number, number][] = puntos.map(([lat, lng]) => [lng, lat]);
  anillo.push([puntos[0][1], puntos[0][0]]); // cerrar el anillo
  try {
    return turf.area(turf.polygon([anillo])) / 10000;
  } catch {
    // Geometría degenerada (puntos repetidos, etc.): no hay área que mostrar.
    return null;
  }
}

export default function AreaEnVivo({ puntos }: { puntos: PuntoLatLng[] }) {
  const area = areaHectareas(puntos);
  if (area === null) {
    return (
      <p className={styles.ayuda}>
        Área en vivo: agrega al menos 3 puntos ({puntos.length} de 3).
      </p>
    );
  }
  return (
    <p className={styles.area} aria-live="polite">
      Área del polígono: {area.toFixed(2)} ha
    </p>
  );
}
