"use client";

import { useCallback, useEffect, useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import SelectorFinca from "@/components/fincas/SelectorFinca";
import FilaLote from "@/components/ganado/FilaLote";
import FormularioCrearLote from "@/components/ganado/FormularioCrearLote";
import EncabezadoPagina from "@/components/ui/EncabezadoPagina";
import EstadoVacio from "@/components/ui/EstadoVacio";
import Tarjeta from "@/components/ui/Tarjeta";
import { useFincaActual } from "@/lib/finca-actual";
import { ganadoApi, type Lote } from "@/lib/ganado";
import { potrerosApi, type PotreroApi } from "@/lib/potreros";
import { rotacionApi, type Movimiento } from "@/lib/rotacion";

function PaginaGanadoInterna() {
  const { fincaId, cargando: cargandoFinca } = useFincaActual();
  const [lotes, setLotes] = useState<Lote[] | null>(null);
  const [potreros, setPotreros] = useState<PotreroApi[]>([]);
  const [sugerencias, setSugerencias] = useState<Movimiento[]>([]);
  const [advertencias, setAdvertencias] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!fincaId) return;
    setError(null);
    try {
      const [l, p] = await Promise.all([
        ganadoApi.listarLotes(fincaId),
        potrerosApi.listar(fincaId),
      ]);
      setLotes(l);
      setPotreros(p);
      // La sugerencia de rotación es la razón de ser del sistema (§7); si
      // falla, el resto de la pantalla sigue siendo útil (fallback manual
      // ordenado por biomasa dentro de FilaLote), así que no se bloquea nada.
      try {
        const rotacion = await rotacionApi.sugerir(fincaId);
        setSugerencias(rotacion.movimientos);
        setAdvertencias(rotacion.advertencias);
      } catch {
        setSugerencias([]);
        setAdvertencias([]);
      }
    } catch {
      setError("No se pudieron cargar los lotes de esta finca.");
    }
  }, [fincaId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Para cada lote, la sugerencia más próxima en el calendario (la primera
  // que devuelve el motor por lote, ya viene ordenada por fecha).
  const sugerenciaPorLote = new Map<string, Movimiento>();
  for (const m of sugerencias) {
    if (!sugerenciaPorLote.has(m.lote_id)) sugerenciaPorLote.set(m.lote_id, m);
  }

  return (
    <section>
      <EncabezadoPagina
        titulo="Ganado"
        descripcion="Lotes de la finca. El sistema sugiere a dónde mover cada lote según biomasa disponible, descanso cumplido y fatiga del potrero — la sugerencia aparece junto a cada lote, no hay que adivinar."
      />

      <div style={{ marginBottom: "1.5rem", maxWidth: "20rem" }}>
        <SelectorFinca />
      </div>

      {cargandoFinca ? (
        <p>Cargando finca…</p>
      ) : !fincaId ? (
        <EstadoVacio
          titulo="No tienes fincas todavía"
          descripcion="Crea una finca antes de registrar lotes."
        />
      ) : (
        <Tarjeta>
          <h2>Registrar lote nuevo</h2>
          <FormularioCrearLote fincaId={fincaId} onCreado={cargar} />

          {error && <p style={{ color: "var(--rojo-700)" }}>{error}</p>}

          {advertencias.length > 0 && (
            <div
              role="status"
              style={{
                background: "var(--ambar-100)",
                color: "var(--ambar-700)",
                border: "1px solid var(--ambar-500)",
                borderRadius: "var(--radio-md)",
                padding: "0.75rem 1rem",
                fontSize: "0.85rem",
                marginBottom: "1rem",
              }}
            >
              {advertencias.map((a) => (
                <p key={a} style={{ margin: 0 }}>
                  ⚠️ {a}
                </p>
              ))}
            </div>
          )}

          {lotes === null ? (
            <p>Cargando lotes…</p>
          ) : lotes.length === 0 ? (
            <EstadoVacio
              titulo="Sin lotes registrados"
              descripcion="Crea el primer lote arriba para empezar a moverlo entre potreros."
            />
          ) : (
            <ul style={{ padding: 0, margin: 0 }}>
              {lotes.map((lote) => (
                <FilaLote
                  key={lote.id}
                  lote={lote}
                  potreros={potreros}
                  sugerencia={sugerenciaPorLote.get(lote.id)}
                  onCambio={cargar}
                />
              ))}
            </ul>
          )}
        </Tarjeta>
      )}
    </section>
  );
}

export default function PaginaGanado() {
  return (
    <RequireAuth>
      <PaginaGanadoInterna />
    </RequireAuth>
  );
}
