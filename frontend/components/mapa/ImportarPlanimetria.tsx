"use client";

/** Import de planimetría (§3.2 del SRP, modos manuales del pipeline).
 *
 * Dos modos, en pestañas separadas:
 *  - Pegar coordenadas: una por línea, "lat, lng"; preview del polígono en el
 *    mapa, área en vivo con Turf y envío por el mismo POST /potreros/.
 *  - Archivo (.kml/.gpx/.csv/.dxf): el parseo/reproyección ocurre en el
 *    backend (§3.2/§3.4); el endpoint aún no existe en esta unidad, así que
 *    por ahora solo se informa al usuario.
 *
 * Usa Leaflet: montar con next/dynamic y ssr: false.
 */

import "leaflet/dist/leaflet.css";
import { useMemo, useState } from "react";
import { MapContainer, Polygon, TileLayer } from "react-leaflet";
import AreaEnVivo from "./AreaEnVivo";
import FormularioPotrero from "./FormularioPotrero";
import { CENTRO_CASANARE, ZOOM_INICIAL } from "./tipos";
import type { PuntoLatLng } from "./tipos";
import styles from "./mapa.module.css";

type Modo = "coordenadas" | "archivo";

interface ResultadoParseo {
  puntos: PuntoLatLng[];
  errores: string[];
}

/** Parsea texto con una coordenada "lat, lng" por línea (WGS84). */
export function parsearCoordenadas(texto: string): ResultadoParseo {
  const puntos: PuntoLatLng[] = [];
  const errores: string[] = [];
  texto.split("\n").forEach((linea, indice) => {
    const limpia = linea.trim();
    if (limpia === "") {
      return;
    }
    const partes = limpia.split(/[,;\s]+/).filter((p) => p !== "");
    const lat = Number(partes[0]);
    const lng = Number(partes[1]);
    if (partes.length !== 2 || !Number.isFinite(lat) || !Number.isFinite(lng)) {
      errores.push(`Línea ${indice + 1}: formato inválido ("${limpia}"). Usa "lat, lng".`);
      return;
    }
    if (Math.abs(lat) > 90 || Math.abs(lng) > 180) {
      errores.push(
        `Línea ${indice + 1}: fuera de rango WGS84 (¿lat y lng invertidas?).`,
      );
      return;
    }
    puntos.push([lat, lng]);
  });
  return { puntos, errores };
}

export default function ImportarPlanimetria() {
  const [modo, setModo] = useState<Modo>("coordenadas");
  const [texto, setTexto] = useState("");
  const [mensajeArchivo, setMensajeArchivo] = useState<string | null>(null);

  const { puntos, errores } = useMemo(() => parsearCoordenadas(texto), [texto]);
  const centro: PuntoLatLng = puntos.length > 0 ? puntos[0] : CENTRO_CASANARE;

  return (
    <div className={styles.contenedor}>
      <div className={styles.tabs} role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={modo === "coordenadas"}
          className={modo === "coordenadas" ? styles.tabActiva : styles.tab}
          onClick={() => setModo("coordenadas")}
        >
          Pegar coordenadas
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={modo === "archivo"}
          className={modo === "archivo" ? styles.tabActiva : styles.tab}
          onClick={() => setModo("archivo")}
        >
          Archivo (KML/GPX/CSV/DXF)
        </button>
      </div>

      {modo === "coordenadas" && (
        <section>
          <label className={styles.campo}>
            Coordenadas del potrero (una por línea, formato «lat, lng» en WGS84)
            <textarea
              className={styles.textareaCoordenadas}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder={"5.3370, -72.3960\n5.3380, -72.3950\n5.3375, -72.3940"}
            />
          </label>
          {errores.length > 0 && (
            <div className={styles.error} role="alert">
              {errores.map((error) => (
                <p key={error}>{error}</p>
              ))}
            </div>
          )}
          <AreaEnVivo puntos={puntos} />
          <MapContainer
            // Remontar el mapa cuando cambia el primer punto para re-centrar
            // la vista previa (center es inmutable tras el montaje).
            key={puntos.length > 0 ? `${centro[0]},${centro[1]}` : "sin-puntos"}
            center={centro}
            zoom={ZOOM_INICIAL}
            className={styles.mapa}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />
            {puntos.length >= 3 && (
              <Polygon
                positions={puntos}
                pathOptions={{ color: "green", fillOpacity: 0.3 }}
              />
            )}
          </MapContainer>
          <p className={styles.ayuda}>
            Vista previa del polígono importado. Corrige el texto de arriba si
            la forma no coincide con el potrero.
          </p>
          <FormularioPotrero puntos={puntos} />
        </section>
      )}

      {modo === "archivo" && (
        <section>
          <label className={styles.campo}>
            Archivo de planimetría (.kml, .gpx, .csv, .dxf)
            <input
              type="file"
              accept=".kml,.gpx,.csv,.dxf"
              onChange={() =>
                setMensajeArchivo(
                  "El import de archivo estará disponible al integrar el backend (pipeline de §3.2/§3.4 con reproyección MAGNA-SIRGAS).",
                )
              }
            />
          </label>
          {mensajeArchivo && (
            <p className={styles.advertencia}>{mensajeArchivo}</p>
          )}
          <p className={styles.ayuda}>
            El archivo se procesará en el servidor (parseo y reproyección a
            WGS84). Mientras tanto puedes usar la pestaña «Pegar coordenadas».
          </p>
        </section>
      )}
    </div>
  );
}
