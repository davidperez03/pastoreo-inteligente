"use client";

/** Mapa de dibujo/edición de potreros (§3.5 del SRP).
 *
 * - Click en el mapa agrega un vértice.
 * - Cada vértice es un Marker arrastrable; al soltarlo se actualiza el punto.
 * - El polígono se pinta en verde con fillOpacity 0.3.
 *
 * Este componente usa Leaflet, que solo funciona en el navegador: debe
 * montarse con next/dynamic y ssr: false.
 */

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import {
  MapContainer,
  Marker,
  Polygon,
  TileLayer,
  useMapEvents,
} from "react-leaflet";
import { CENTRO_CASANARE, ZOOM_INICIAL } from "./tipos";
import type { PuntoLatLng } from "./tipos";
import styles from "./mapa.module.css";

const iconoVertice = L.divIcon({
  className: styles.vertice,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

interface PropsMapaPotreros {
  puntos: PuntoLatLng[];
  onAgregarPunto: (punto: PuntoLatLng) => void;
  onMoverPunto: (indice: number, punto: PuntoLatLng) => void;
  onDeshacer: () => void;
  onLimpiar: () => void;
}

/** Captura los clicks sobre el mapa y los convierte en vértices nuevos. */
function CapturaClicks({
  onClick,
}: {
  onClick: (punto: PuntoLatLng) => void;
}) {
  useMapEvents({
    click: (evento) => onClick([evento.latlng.lat, evento.latlng.lng]),
  });
  return null;
}

export default function MapaPotreros({
  puntos,
  onAgregarPunto,
  onMoverPunto,
  onDeshacer,
  onLimpiar,
}: PropsMapaPotreros) {
  return (
    <div>
      <MapContainer
        center={CENTRO_CASANARE}
        zoom={ZOOM_INICIAL}
        className={styles.mapa}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        <CapturaClicks onClick={onAgregarPunto} />
        {puntos.length >= 3 && (
          <Polygon
            positions={puntos}
            pathOptions={{ color: "green", fillOpacity: 0.3 }}
          />
        )}
        {puntos.map((posicion, i) => (
          <Marker
            key={i}
            position={posicion}
            draggable
            icon={iconoVertice}
            eventHandlers={{
              dragend: (evento) => {
                const marcador = evento.target as L.Marker;
                const { lat, lng } = marcador.getLatLng();
                onMoverPunto(i, [lat, lng]);
              },
            }}
          />
        ))}
      </MapContainer>
      <div className={styles.botonera}>
        <button
          type="button"
          className={styles.boton}
          onClick={onDeshacer}
          disabled={puntos.length === 0}
        >
          Deshacer último punto
        </button>
        <button
          type="button"
          className={styles.boton}
          onClick={onLimpiar}
          disabled={puntos.length === 0}
        >
          Limpiar
        </button>
      </div>
      <p className={styles.ayuda}>
        Haz click en el mapa para agregar vértices; arrastra un vértice para
        corregirlo.
      </p>
    </div>
  );
}
