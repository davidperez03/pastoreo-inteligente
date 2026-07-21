"use client";

/** Página de importación de planimetría (coordenadas pegadas o archivo).
 * ImportarPlanimetria usa Leaflet para la vista previa, así que se monta con
 * next/dynamic y ssr: false. */

import dynamic from "next/dynamic";
import Link from "next/link";
import RequireAuth from "@/components/auth/RequireAuth";
import styles from "@/components/mapa/mapa.module.css";

const ImportarPlanimetria = dynamic(
  () => import("@/components/mapa/ImportarPlanimetria"),
  { ssr: false, loading: () => <p>Cargando importador…</p> },
);

export default function PaginaImportar() {
  return (
    <RequireAuth>
      <section className={styles.contenedor}>
        <h1>Importar planimetría de potrero</h1>
        <div className={styles.tabs}>
          <Link href="/mapa" className={styles.tab}>
            Dibujar en el mapa
          </Link>
          <span className={styles.tabActiva}>
            Importar (coordenadas o archivo)
          </span>
        </div>
        <ImportarPlanimetria />
      </section>
    </RequireAuth>
  );
}
