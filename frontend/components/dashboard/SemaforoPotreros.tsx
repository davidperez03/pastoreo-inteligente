import Link from "next/link";
import type { EstadoPotrero, PotreroResumen } from "./tipos";
import styles from "./dashboard.module.css";

const ETIQUETA_ESTADO: Record<EstadoPotrero, string> = {
  listo: "Listo para pastoreo",
  descanso: "En recuperación",
  ocupado: "En uso",
};

const CLASE_TARJETA: Record<EstadoPotrero, string> = {
  listo: styles.tarjetaListo,
  descanso: styles.tarjetaDescanso,
  ocupado: styles.tarjetaOcupado,
};

const CLASE_INSIGNIA: Record<EstadoPotrero, string> = {
  listo: styles.insigniaListo,
  descanso: styles.insigniaDescanso,
  ocupado: styles.insigniaOcupado,
};

function formatearBiomasa(valor: number | null): string {
  return valor === null ? "sin dato" : `${valor.toLocaleString("es-CO")} kg MS/ha`;
}

/** Grid semáforo: una tarjeta por potrero, coloreada por estado
 * (verde=listo, ámbar=descanso, rojo=ocupado) y siempre con etiqueta de
 * texto del estado. Click lleva al detalle/historial del potrero. */
export default function SemaforoPotreros({
  potreros,
}: {
  potreros: PotreroResumen[];
}) {
  if (potreros.length === 0) {
    return <p className={styles.vacio}>No hay potreros registrados en la finca.</p>;
  }
  return (
    <div className={styles.gridPotreros}>
      {potreros.map((p) => (
        <Link
          key={p.id}
          href={`/dashboard/potrero/${p.id}`}
          className={`${styles.tarjeta} ${CLASE_TARJETA[p.estado]}`}
        >
          <div className={styles.tarjetaCabecera}>
            <span className={styles.tarjetaNombre}>{p.nombre}</span>
            <span className={`${styles.insignia} ${CLASE_INSIGNIA[p.estado]}`}>
              {ETIQUETA_ESTADO[p.estado]}
            </span>
          </div>
          <dl className={styles.tarjetaDatos}>
            <div className={styles.dato}>
              <dt>Área</dt>
              <dd>{p.area_ha.toLocaleString("es-CO")} ha</dd>
            </div>
            <div className={styles.dato}>
              <dt>Biomasa</dt>
              <dd>{formatearBiomasa(p.biomasa_kg_ms_ha)}</dd>
            </div>
            <div className={styles.dato}>
              <dt>Factor fatiga</dt>
              <dd>{p.factor_fatiga.toFixed(2)}</dd>
            </div>
            <div className={styles.dato}>
              <dt>Días en estado</dt>
              <dd>{p.dias_en_estado === null ? "—" : p.dias_en_estado}</dd>
            </div>
          </dl>
        </Link>
      ))}
    </div>
  );
}
