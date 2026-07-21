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
import EncabezadoPagina from "@/components/ui/EncabezadoPagina";
import EstadoVacio from "@/components/ui/EstadoVacio";
import { useFincaActual } from "@/lib/finca-actual";
import styles from "@/components/dashboard/dashboard.module.css";

interface EstadoDashboard {
  potreros: PotreroResumen[];
  lotes: LoteResumen[];
  sugerencias: Sugerencia[];
  esMock: boolean;
}

/** Dashboard principal: semáforo de estado por potrero, lotes de ganado y
 * próximos movimientos sugeridos por el motor de rotación. */
function PaginaDashboardInterna() {
  const { fincaId, cargando: cargandoFinca } = useFincaActual();
  const [datos, setDatos] = useState<EstadoDashboard | null>(null);

  useEffect(() => {
    if (!fincaId) return;
    let activo = true;
    setDatos(null);
    Promise.all([
      obtenerPotreros(fincaId),
      obtenerLotes(fincaId),
      obtenerSugerencias(fincaId),
    ]).then(([potreros, lotes, sugerencias]) => {
      if (!activo) return;
      setDatos({
        potreros: potreros.datos,
        lotes: lotes.datos,
        sugerencias: sugerencias.datos,
        esMock: potreros.esMock || lotes.esMock || sugerencias.esMock,
      });
    });
    return () => {
      activo = false;
    };
  }, [fincaId]);

  return (
    <section>
      <EncabezadoPagina
        titulo="Dashboard de potreros"
        descripcion="Estado de cada potrero (semáforo), lotes de ganado y sugerencias de rotación."
      />

      {cargandoFinca ? (
        <p className={styles.cargando}>Cargando finca…</p>
      ) : !fincaId ? (
        <EstadoVacio
          titulo="No tienes fincas todavía"
          descripcion="Crea una finca para empezar a ver su estado aquí."
        />
      ) : datos === null ? (
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
  );
}

export default function PaginaDashboard() {
  return (
    <RequireAuth>
      <PaginaDashboardInterna />
    </RequireAuth>
  );
}
