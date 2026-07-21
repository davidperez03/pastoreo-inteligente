"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import GraficoHistorial from "@/components/dashboard/GraficoHistorial";
import { obtenerHistorial, obtenerPotreros } from "@/components/dashboard/datos";
import type { PotreroResumen, PuntoHistorial } from "@/components/dashboard/tipos";
import { useFincaActual } from "@/lib/finca-actual";
import styles from "@/components/dashboard/dashboard.module.css";

const ETIQUETA_ESTADO: Record<PotreroResumen["estado"], string> = {
  listo: "Listo para pastoreo",
  descanso: "En recuperación",
  ocupado: "En uso",
};

interface EstadoDetalle {
  potrero: PotreroResumen | null;
  historial: PuntoHistorial[];
  esMock: boolean;
}

/** Detalle e historial de un potrero (§9 y §16): compara la biomasa que
 * estima el modelo con las lecturas NDVI del satélite y los eventos reales
 * de manejo — la base de confianza del ganadero en las sugerencias. */
function PaginaDetallePotreroInterna() {
  const params = useParams<{ id: string }>();
  const potreroId = params.id;
  const { fincaId } = useFincaActual();
  const [datos, setDatos] = useState<EstadoDetalle | null>(null);

  useEffect(() => {
    if (!potreroId || !fincaId) return;
    let activo = true;
    Promise.all([obtenerHistorial(potreroId), obtenerPotreros(fincaId)]).then(
      ([historial, potreros]) => {
        if (!activo) return;
        setDatos({
          potrero: potreros.datos.find((p) => p.id === potreroId) ?? null,
          historial: historial.datos,
          esMock: historial.esMock || potreros.esMock,
        });
      },
    );
    return () => {
      activo = false;
    };
  }, [potreroId, fincaId]);

  const nombre = datos?.potrero?.nombre ?? potreroId;

  return (
    <section>
      <nav className={styles.migas} aria-label="Miga de pan">
        <Link href="/dashboard">← Volver al dashboard</Link>
      </nav>
      <h1>Potrero {nombre}</h1>

      {datos === null ? (
        <p className={styles.cargando}>Cargando historial del potrero…</p>
      ) : (
        <>
          {datos.esMock && (
            <p className={styles.bandaMock} role="status">
              Datos de demostración — no hay conexión con el backend. Las
              cifras que se muestran son sintéticas.
            </p>
          )}

          {datos.potrero !== null && (
            <div className={styles.fichaPotrero}>
              <span className={styles.chip}>
                Estado
                <strong>{ETIQUETA_ESTADO[datos.potrero.estado]}</strong>
              </span>
              <span className={styles.chip}>
                Área
                <strong>{datos.potrero.area_ha.toLocaleString("es-CO")} ha</strong>
              </span>
              <span className={styles.chip}>
                Biomasa actual
                <strong>
                  {datos.potrero.biomasa_kg_ms_ha === null
                    ? "sin dato"
                    : `${datos.potrero.biomasa_kg_ms_ha.toLocaleString("es-CO")} kg MS/ha`}
                </strong>
              </span>
              <span className={styles.chip}>
                Factor fatiga
                <strong>{datos.potrero.factor_fatiga.toFixed(2)}</strong>
              </span>
              <span className={styles.chip}>
                Días en estado
                <strong>
                  {datos.potrero.dias_en_estado === null ? "—" : datos.potrero.dias_en_estado}
                </strong>
              </span>
            </div>
          )}

          <div className={styles.seccion}>
            <h2>Historial de biomasa (últimos 90 días)</h2>
            <GraficoHistorial puntos={datos.historial} />
            <p className={styles.explicacion}>
              La línea azul es la biomasa que estima el modelo agronómico día a
              día; los puntos naranja son las lecturas NDVI del satélite (una
              medición independiente de la realidad); las marcas verticales
              (E/S) son las entradas y salidas reales de ganado. Cuando el
              modelo, el satélite y el manejo real cuentan la misma historia,
              las sugerencias de rotación son confiables — y cuando divergen,
              el sistema se recalibra con las lecturas del satélite.
            </p>
          </div>
        </>
      )}
    </section>
  );
}

export default function PaginaDetallePotrero() {
  return (
    <RequireAuth>
      <PaginaDetallePotreroInterna />
    </RequireAuth>
  );
}
