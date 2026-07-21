import type { LoteResumen, PotreroResumen, SugerenciaRotacion } from "./tipos";
import styles from "./dashboard.module.css";

function formatearFecha(fechaIso: string): string {
  const [anio, mes, dia] = fechaIso.split("-").map(Number);
  if (!anio || !mes || !dia) return fechaIso;
  // Fecha local (sin zona horaria) para no correr el día por UTC.
  return new Intl.DateTimeFormat("es-CO", {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(new Date(anio, mes - 1, dia));
}

/** Próximos movimientos sugeridos por el motor de rotación:
 * lote → potrero destino, con fecha estimada. */
export default function SugerenciasRotacion({
  sugerencias,
  lotes,
  potreros,
}: {
  sugerencias: SugerenciaRotacion[];
  lotes: LoteResumen[];
  potreros: PotreroResumen[];
}) {
  if (sugerencias.length === 0) {
    return (
      <p className={styles.vacio}>
        No hay movimientos sugeridos por ahora — los lotes pueden permanecer
        donde están.
      </p>
    );
  }
  const nombreLote = new Map(lotes.map((l) => [l.id, l.nombre]));
  const nombrePotrero = new Map(potreros.map((p) => [p.id, p.nombre]));
  return (
    <table className={styles.tabla}>
      <thead>
        <tr>
          <th>Movimiento sugerido</th>
          <th>Fecha estimada</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {sugerencias.map((s) => (
          <tr key={`${s.lote_id}-${s.potrero_id}-${s.fecha}`}>
            <td className={styles.movimiento}>
              {nombreLote.get(s.lote_id) ?? s.lote_id}
              <span className={styles.flecha} aria-hidden="true">
                →
              </span>
              {nombrePotrero.get(s.potrero_id) ?? s.potrero_id}
            </td>
            <td>{formatearFecha(s.fecha)}</td>
            <td>
              <a href="/ganado" style={{ fontSize: "0.85rem", whiteSpace: "nowrap" }}>
                Registrar en Ganado →
              </a>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
