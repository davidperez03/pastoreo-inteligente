"use client";

import { useState } from "react";
import RequireAuth from "@/components/auth/RequireAuth";
import Boton from "@/components/ui/Boton";
import { Campo } from "@/components/ui/Campo";
import EncabezadoPagina from "@/components/ui/EncabezadoPagina";
import EstadoVacio from "@/components/ui/EstadoVacio";
import Tarjeta from "@/components/ui/Tarjeta";
import { useFincaActual } from "@/lib/finca-actual";
import { fincasApi } from "@/lib/fincas";

function PaginaFincasInterna() {
  const { fincas, fincaId, seleccionar, recargar, cargando } = useFincaActual();
  const [nombre, setNombre] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const nueva = await fincasApi.crear(nombre);
      setNombre("");
      await recargar();
      seleccionar(nueva.id);
    } catch {
      setError("No se pudo crear la finca.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section>
      <EncabezadoPagina
        titulo="Fincas"
        descripcion="Las fincas de tu organización. La finca activa determina qué potreros, lotes y sugerencias ves en el resto de la app."
      />

      <Tarjeta style={{ marginBottom: "1.5rem" }}>
        <h2>Nueva finca</h2>
        <form onSubmit={crear} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <Campo
              etiqueta="Nombre"
              required
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Ej. La Esperanza"
            />
          </div>
          <Boton type="submit" cargando={enviando} style={{ marginBottom: "1rem" }}>
            Crear
          </Boton>
        </form>
        {error && <p style={{ color: "var(--rojo-700)" }}>{error}</p>}
      </Tarjeta>

      {cargando ? (
        <p>Cargando…</p>
      ) : fincas.length === 0 ? (
        <EstadoVacio titulo="Aún no hay fincas" descripcion="Crea la primera arriba." />
      ) : (
        <Tarjeta>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {fincas.map((f) => (
              <li
                key={f.id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "0.75rem 0",
                  borderBottom: "1px solid var(--borde)",
                }}
              >
                <span style={{ fontWeight: 600 }}>{f.nombre}</span>
                {f.id === fincaId ? (
                  <span style={{ color: "var(--primario)", fontSize: "0.85rem", fontWeight: 600 }}>
                    Activa
                  </span>
                ) : (
                  <Boton variante="secundario" onClick={() => seleccionar(f.id)}>
                    Usar esta finca
                  </Boton>
                )}
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}
    </section>
  );
}

export default function PaginaFincas() {
  return (
    <RequireAuth>
      <PaginaFincasInterna />
    </RequireAuth>
  );
}
