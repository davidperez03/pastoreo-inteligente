"use client";

import { useFincaActual } from "@/lib/finca-actual";

/** Selector compacto de finca activa — usado en el nav y en páginas que
 * necesitan operar sobre "la finca actual". */
export default function SelectorFinca() {
  const { fincas, fincaId, seleccionar, cargando } = useFincaActual();

  if (cargando) return null;
  if (fincas.length === 0) {
    return (
      <a href="/fincas" style={{ fontSize: "0.85rem" }}>
        + Crear finca
      </a>
    );
  }

  return (
    <select
      aria-label="Finca activa"
      value={fincaId ?? ""}
      onChange={(e) => seleccionar(e.target.value)}
    >
      {fincas.map((f) => (
        <option key={f.id} value={f.id}>
          {f.nombre}
        </option>
      ))}
    </select>
  );
}
