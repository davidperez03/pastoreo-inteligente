import type { LoteResumen, PotreroResumen } from "./tipos";
import styles from "./dashboard.module.css";

/** Tabla de lotes de ganado con número de animales, UA equivalentes y el
 * potrero donde está cada lote (nombre resuelto contra la lista de potreros). */
export default function TablaLotes({
  lotes,
  potreros,
}: {
  lotes: LoteResumen[];
  potreros: PotreroResumen[];
}) {
  if (lotes.length === 0) {
    return <p className={styles.vacio}>No hay lotes registrados.</p>;
  }
  const nombrePotrero = new Map(potreros.map((p) => [p.id, p.nombre]));
  return (
    <table className={styles.tabla}>
      <thead>
        <tr>
          <th>Lote</th>
          <th className={styles.numero}>Animales</th>
          <th className={styles.numero}>UA equivalente</th>
          <th>Potrero actual</th>
        </tr>
      </thead>
      <tbody>
        {lotes.map((lote) => (
          <tr key={lote.id}>
            <td>{lote.nombre}</td>
            <td className={styles.numero}>{lote.n_animales}</td>
            <td className={styles.numero}>{lote.ua_equivalente.toFixed(1)}</td>
            <td>
              {lote.potrero_actual_id === null
                ? "Sin asignar"
                : (nombrePotrero.get(lote.potrero_actual_id) ??
                  lote.potrero_actual_id)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
