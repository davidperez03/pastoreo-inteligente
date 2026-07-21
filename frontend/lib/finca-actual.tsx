"use client";

/** Contexto de "finca actual": qué finca ve el usuario en el resto de la
 * app (mapa, dashboard, ganado). Reemplaza el FINCA_DEMO_ID hardcodeado.
 *
 * Se carga la lista de fincas de la organización al iniciar sesión; si no
 * hay ninguna seleccionada (o la guardada ya no existe), se toma la
 * primera. La selección persiste en localStorage entre visitas. */

import { createContext, useContext, useEffect, useState } from "react";
import { useAuth } from "./auth";
import { fincasApi, type Finca } from "./fincas";

const CLAVE_STORAGE = "srp_finca_id";

interface FincaActualState {
  fincas: Finca[];
  fincaId: string | null;
  finca: Finca | null;
  cargando: boolean;
  error: string | null;
  seleccionar: (id: string) => void;
  recargar: () => Promise<void>;
}

const Ctx = createContext<FincaActualState | null>(null);

export function FincaActualProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [fincas, setFincas] = useState<Finca[]>([]);
  const [fincaId, setFincaId] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function cargar() {
    setCargando(true);
    setError(null);
    try {
      const lista = await fincasApi.listar();
      setFincas(lista);
      const guardada =
        typeof window !== "undefined" ? sessionStorage.getItem(CLAVE_STORAGE) : null;
      const valida = lista.find((f) => f.id === guardada);
      setFincaId(valida ? valida.id : (lista[0]?.id ?? null));
    } catch {
      setError("No se pudo cargar la lista de fincas.");
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    if (user) {
      cargar();
    } else {
      setFincas([]);
      setFincaId(null);
      setCargando(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  function seleccionar(id: string) {
    setFincaId(id);
    if (typeof window !== "undefined") sessionStorage.setItem(CLAVE_STORAGE, id);
  }

  const value: FincaActualState = {
    fincas,
    fincaId,
    finca: fincas.find((f) => f.id === fincaId) ?? null,
    cargando,
    error,
    seleccionar,
    recargar: cargar,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFincaActual(): FincaActualState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFincaActual debe usarse dentro de <FincaActualProvider>");
  return ctx;
}
