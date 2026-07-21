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

function PaginaGanadoInterna() {
  const { fincaId, cargando: cargandoFinca } = useFincaActual();
  const [lotes, setLotes] = useState<Lote[] | null>(null);
  const [potreros, setPotreros] = useState<PotreroApi[]>([]);
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
    } catch {
      setError("No se pudieron cargar los lotes de esta finca.");
    }
  }, [fincaId]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  return (
    <section>
      <EncabezadoPagina
        titulo="Ganado"
        descripcion="Lotes de la finca y registro de entrada/salida de potreros — el movimiento real que alimenta la calibración del modelo."
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
                <FilaLote key={lote.id} lote={lote} potreros={potreros} onCambio={cargar} />
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
