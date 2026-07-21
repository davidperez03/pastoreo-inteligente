"use client";

import { useEffect, useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import SemaforoPotreros from "@/components/dashboard/SemaforoPotreros";
import SugerenciasRotacion from "@/components/dashboard/SugerenciasRotacion";
import TablaLotes from "@/components/dashboard/TablaLotes";
import {
  obtenerLotes,
  obtenerPotreros,
  obtenerSugerencias,
} from "@/components/dashboard/datos";
import type {
  LoteResumen,
  PotreroResumen,
  SugerenciaRotacion as Sugerencia,
} from "@/components/dashboard/tipos";
import styles from "@/components/dashboard/dashboard.module.css";

interface EstadoDashboard {
  potreros: PotreroResumen[];
  lotes: LoteResumen[];
  sugerencias: Sugerencia[];
  esMock: boolean;
}

/** Dashboard principal (Unidad 10): semáforo de estado por potrero,
 * lotes de ganado y próximos movimientos sugeridos por el motor de rotación. */
export default function PaginaDashboard() {
  const [datos, setDatos] = useState<EstadoDashboard | null>(null);

  useEffect(() => {
    let activo = true;
    Promise.all([obtenerPotreros(), obtenerLotes(), obtenerSugerencias()]).then(
      ([potreros, lotes, sugerencias]) => {
        if (!activo) return;
        setDatos({
          potreros: potreros.datos,
          lotes: lotes.datos,
          sugerencias: sugerencias.datos,
          esMock: potreros.esMock || lotes.esMock || sugerencias.esMock,
        });
      },
    );
    return () => {
      activo = false;
    };
  }, []);

  return (
    <RequireAuth>
      <section>
        <h1>Dashboard de potreros</h1>
        <p className={styles.subtitulo}>
          Estado de cada potrero (semáforo), lotes de ganado y sugerencias de
          rotación.
        </p>

        {datos === null ? (
          <p className={styles.cargando}>Cargando estado de la finca…</p>
        ) : (
          <>
            {datos.esMock && (
              <p className={styles.bandaMock} role="status">
                Datos de demostración — no hay conexión con el backend. Las
                cifras que se muestran son sintéticas.
              </p>
            )}

            <div className={styles.seccion}>
              <h2>Potreros</h2>
              <SemaforoPotreros potreros={datos.potreros} />
            </div>

            <div className={styles.seccion}>
              <h2>Lotes de ganado</h2>
              <TablaLotes lotes={datos.lotes} potreros={datos.potreros} />
            </div>

            <div className={styles.seccion}>
              <h2>Próximos movimientos sugeridos</h2>
              <SugerenciasRotacion
                sugerencias={datos.sugerencias}
                lotes={datos.lotes}
                potreros={datos.potreros}
              />
            </div>
          </>
        )}
      </section>
    </RequireAuth>
  );
}
