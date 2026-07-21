"use client";

import { useState } from "react";
import Boton from "@/components/ui/Boton";
import Insignia from "@/components/ui/Insignia";
import { ganadoApi, type Lote } from "@/lib/ganado";
import type { PotreroApi } from "@/lib/potreros";
import s from "./ganado.module.css";

/** Una fila por lote: si está libre, ofrece "Registrar entrada" (elegir
 * potrero); si está ocupando un potrero, ofrece "Registrar salida" (con
 * biomasa final opcional, el dato que alimenta la calibración §8). */
export default function FilaLote({
  lote,
  potreros,
  onCambio,
}: {
  lote: Lote;
  potreros: PotreroApi[];
  onCambio: () => void;
}) {
  const [accionAbierta, setAccionAbierta] = useState(false);
  const [potreroId, setPotreroId] = useState("");
  const [biomasa, setBiomasa] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const potreroActual = potreros.find((p) => p.id === lote.potrero_actual_id);
  const disponibles = potreros.filter((p) => p.estado !== "ocupado");
  // Referencia (no reemplazo) para quien está midiendo en campo: el potrero
  // de salida es siempre el actual; el de entrada es el que se va eligiendo
  // en el select. Usar este número tal cual sería circular para la
  // calibración (§8) — el sistema no puede corregirse con su propia
  // predicción — pero ayuda a saber qué espera el modelo.
  const potreroReferencia = lote.potrero_actual_id
    ? potreroActual
    : potreros.find((p) => p.id === potreroId);

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
    <li className={s.filaLote} style={{ listStyle: "none", padding: "0.9rem 0", borderBottom: "1px solid var(--borde)" }}>
      <div className={s.filaLote__info}>
        <span className={s.filaLote__nombre}>{lote.nombre ?? "(sin nombre)"}</span>
        <span className={s.filaLote__meta}>
          {lote.n_animales} animales · {lote.ua_equivalente.toFixed(1)} UA
          {potreroActual && <> · en <strong>{potreroActual.nombre}</strong></>}
        </span>
      </div>

      {!accionAbierta ? (
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Insignia color={lote.potrero_actual_id ? "rojo" : "verde"}>
            {lote.potrero_actual_id ? "Ocupando potrero" : "Libre"}
          </Insignia>
          <Boton variante="secundario" onClick={() => setAccionAbierta(true)}>
            {lote.potrero_actual_id ? "Registrar salida" : "Registrar entrada"}
          </Boton>
        </div>
      ) : (
        <div className={s.accionInline}>
          {!lote.potrero_actual_id && (
            <select value={potreroId} onChange={(e) => setPotreroId(e.target.value)}>
              <option value="">Elegir potrero…</option>
              {disponibles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre} ({p.estado})
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
          {error && <span className="campoError" style={{ color: "var(--rojo-700)", fontSize: "0.8rem" }}>{error}</span>}
        </div>
      )}
    </li>
  );
}
