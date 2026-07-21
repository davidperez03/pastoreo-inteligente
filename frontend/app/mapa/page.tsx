"use client";

/** Página de dibujo/edición de potreros sobre el mapa (§3.5 del SRP).
 *
 * El componente Leaflet se monta con next/dynamic y ssr: false porque
 * react-leaflet no funciona en SSR (depende de window).
 */

import { useCallback, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import AreaEnVivo from "@/components/mapa/AreaEnVivo";
import FormularioPotrero from "@/components/mapa/FormularioPotrero";
import type { PuntoLatLng } from "@/components/mapa/tipos";
import styles from "@/components/mapa/mapa.module.css";

const MapaPotreros = dynamic(() => import("@/components/mapa/MapaPotreros"), {
  ssr: false,
  loading: () => <p>Cargando mapa…</p>,
});

export default function PaginaMapa() {
  const [puntos, setPuntos] = useState<PuntoLatLng[]>([]);

  const agregarPunto = useCallback((punto: PuntoLatLng) => {
    setPuntos((previos) => [...previos, punto]);
  }, []);
  const moverPunto = useCallback((indice: number, punto: PuntoLatLng) => {
    setPuntos((previos) =>
      previos.map((p, i) => (i === indice ? punto : p)),
    );
  }, []);
  const deshacer = useCallback(() => {
    setPuntos((previos) => previos.slice(0, -1));
  }, []);
  const limpiar = useCallback(() => {
    setPuntos([]);
  }, []);

  return (
    <section className={styles.contenedor}>
      <h1>Potreros — dibujar en el mapa</h1>
      <div className={styles.tabs}>
        <span className={styles.tabActiva}>Dibujar en el mapa</span>
        <Link href="/mapa/importar" className={styles.tab}>
          Importar (coordenadas o archivo)
        </Link>
      </div>
      <MapaPotreros
        puntos={puntos}
        onAgregarPunto={agregarPunto}
        onMoverPunto={moverPunto}
        onDeshacer={deshacer}
        onLimpiar={limpiar}
      />
      <AreaEnVivo puntos={puntos} />
      <FormularioPotrero puntos={puntos} />
    </section>
  );
}
