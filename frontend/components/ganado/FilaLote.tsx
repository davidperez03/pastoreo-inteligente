"use client";

import { useState } from "react";
import Boton from "@/components/ui/Boton";
import Insignia from "@/components/ui/Insignia";
import { ganadoApi, type Lote } from "@/lib/ganado";
import type { PotreroApi } from "@/lib/potreros";
import type { Movimiento } from "@/lib/rotacion";
import s from "./ganado.module.css";

function formatearFecha(iso: string): string {
  const hoy = new Date().toISOString().slice(0, 10);
  if (iso === hoy) return "hoy";
  return new Date(`${iso}T00:00:00`).toLocaleDateString("es-CO", {
    day: "numeric",
    month: "short",
  });
}

/** Una fila por lote: si está libre, ofrece "Registrar entrada" (con el
 * potrero que sugiere el motor de rotación §7 destacado, o elegir otro);
 * si está ocupando un potrero, ofrece "Registrar salida" (con biomasa final
 * opcional, el dato que alimenta la calibración §8). */
export default function FilaLote({
  lote,
  potreros,
  sugerencia,
  onCambio,
}: {
  lote: Lote;
  potreros: PotreroApi[];
  sugerencia?: Movimiento;
  onCambio: () => void;
}) {
  const [accionAbierta, setAccionAbierta] = useState(false);
  const [potreroId, setPotreroId] = useState("");
  const [biomasa, setBiomasa] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const potreroActual = potreros.find((p) => p.id === lote.potrero_actual_id);
  const potreroSugerido = sugerencia
    ? potreros.find((p) => p.id === sugerencia.potrero_id)
    : undefined;

  // Sin sugerencia específica (el motor no encontró candidato, o la llamada
  // falló), al menos no queda un dropdown alfabético ciego: se ordena por lo
  // mismo que pesa el motor — más biomasa aprovechable y menos fatiga primero.
  const disponibles = [...potreros]
    .filter((p) => p.estado !== "ocupado")
    .sort((a, b) => {
      const biomasaA = a.biomasa_actual_kg_ms_ha ?? -1;
      const biomasaB = b.biomasa_actual_kg_ms_ha ?? -1;
      if (biomasaB !== biomasaA) return biomasaB - biomasaA;
      return b.factor_fatiga - a.factor_fatiga;
    });

  const potreroReferencia = lote.potrero_actual_id ? potreroActual : potreroSugerido;

  function abrirConSugerencia() {
    if (potreroSugerido) setPotreroId(potreroSugerido.id);
    setAccionAbierta(true);
  }

  async function confirmar() {
    setEnviando(true);
    setError(null);
    try {
      if (lote.potrero_actual_id) {
        await ganadoApi.registrarSalida({
          lote_id: lote.id,
          biomasa_final: biomasa ? Number(biomasa) : undefined,
        });
      } else {
        if (!potreroId) {
          setError("Elige un potrero.");
          setEnviando(false);
          return;
        }
        await ganadoApi.registrarEntrada({
          lote_id: lote.id,
          potrero_id: potreroId,
          biomasa_inicial: biomasa ? Number(biomasa) : undefined,
        });
      }
      setAccionAbierta(false);
      setBiomasa("");
      setPotreroId("");
      onCambio();
    } catch {
      setError("No se pudo registrar el movimiento. Intenta de nuevo.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <li
      className={s.filaLote}
      style={{ listStyle: "none", padding: "0.9rem 0", borderBottom: "1px solid var(--borde)" }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
        <div className={s.filaLote__info}>
          <span className={s.filaLote__nombre}>{lote.nombre ?? "(sin nombre)"}</span>
          <span className={s.filaLote__meta}>
            {lote.n_animales} animales · {lote.ua_equivalente.toFixed(1)} UA
            {potreroActual && (
              <>
                {" "}
                · en <strong>{potreroActual.nombre}</strong>
              </>
            )}
          </span>
        </div>

        {!accionAbierta && (
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <Insignia color={lote.potrero_actual_id ? "rojo" : "verde"}>
              {lote.potrero_actual_id ? "Ocupando potrero" : "Libre"}
            </Insignia>
            <Boton variante="secundario" onClick={() => setAccionAbierta(true)}>
              {lote.potrero_actual_id ? "Registrar salida" : "Registrar entrada"}
            </Boton>
          </div>
        )}
      </div>

      {/* Recomendación del motor de rotación (§7) — siempre visible, no hay
       * que ir al dashboard a buscarla. Un solo clic la acepta. */}
      {!accionAbierta && !lote.potrero_actual_id && potreroSugerido && (
        <div
          style={{
            marginTop: "0.6rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.75rem",
            flexWrap: "wrap",
            background: "var(--verde-50)",
            border: "1px solid var(--verde-200)",
            borderRadius: "var(--radio-md)",
            padding: "0.6rem 0.85rem",
          }}
        >
          <span style={{ fontSize: "0.85rem" }}>
            🎯 El sistema sugiere mover a <strong>{potreroSugerido.nombre}</strong>
            {" "}
            ({potreroSugerido.biomasa_actual_kg_ms_ha != null
              ? `${Math.round(potreroSugerido.biomasa_actual_kg_ms_ha)} kg MS/ha, `
              : ""}
            factor {potreroSugerido.factor_fatiga.toFixed(2)}) — {formatearFecha(sugerencia!.fecha)}
          </span>
          <Boton onClick={abrirConSugerencia}>Usar esta sugerencia</Boton>
        </div>
      )}
      {!accionAbierta && lote.potrero_actual_id && sugerencia && (
        <p style={{ marginTop: "0.5rem", fontSize: "0.82rem", color: "var(--ambar-700)" }}>
          🕐 El sistema sugiere moverlo {formatearFecha(sugerencia.fecha)} — registra la salida
          cuando corresponda.
        </p>
      )}

      {accionAbierta && (
        <div className={s.accionInline} style={{ marginTop: "0.6rem" }}>
          {!lote.potrero_actual_id && (
            <select value={potreroId} onChange={(e) => setPotreroId(e.target.value)}>
              <option value="">Elegir potrero…</option>
              {potreroSugerido && (
                <option value={potreroSugerido.id}>⭐ {potreroSugerido.nombre} (sugerido)</option>
              )}
              {disponibles
                .filter((p) => p.id !== potreroSugerido?.id)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre} ({p.estado}
                    {p.biomasa_actual_kg_ms_ha != null
                      ? `, ${Math.round(p.biomasa_actual_kg_ms_ha)} kg MS/ha`
                      : ""}
                    )
                  </option>
                ))}
            </select>
          )}
          <div>
            <input
              type="number"
              min={0}
              placeholder={lote.potrero_actual_id ? "Biomasa final (opcional)" : "Biomasa inicial (opcional)"}
              value={biomasa}
              onChange={(e) => setBiomasa(e.target.value)}
            />
            <p style={{ fontSize: "0.75rem", color: "var(--texto-tenue)", margin: "0.2rem 0 0" }}>
              kg MS/ha, medido en campo (disco de pastura o corte y pesaje) — mejor que
              un dato de ojo.{" "}
              {potreroReferencia?.biomasa_actual_kg_ms_ha != null && (
                <>El modelo estima ahora mismo {Math.round(potreroReferencia.biomasa_actual_kg_ms_ha)} kg MS/ha.</>
              )}
            </p>
          </div>
          <Boton onClick={confirmar} cargando={enviando}>
            Confirmar
          </Boton>
          <Boton variante="fantasma" onClick={() => setAccionAbierta(false)} disabled={enviando}>
            Cancelar
          </Boton>
          {error && (
            <span className="campoError" style={{ color: "var(--rojo-700)", fontSize: "0.8rem" }}>
              {error}
            </span>
          )}
        </div>
      )}
    </li>
  );
}
