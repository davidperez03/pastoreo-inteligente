"use client";

import { useState } from "react";
import Boton from "@/components/ui/Boton";
import { Campo } from "@/components/ui/Campo";
import { ganadoApi } from "@/lib/ganado";
import s from "./ganado.module.css";

export default function FormularioCrearLote({
  fincaId,
  onCreado,
}: {
  fincaId: string;
  onCreado: () => void;
}) {
  const [nombre, setNombre] = useState("");
  const [nAnimales, setNAnimales] = useState("");
  const [peso, setPeso] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await ganadoApi.crearLote({
        finca_id: fincaId,
        nombre,
        n_animales: Number(nAnimales),
        peso_promedio_kg: Number(peso),
      });
      setNombre("");
      setNAnimales("");
      setPeso("");
      onCreado();
    } catch {
      setError("No se pudo crear el lote.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className={s.formCrear}>
      <Campo
        etiqueta="Nombre del lote"
        required
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
      />
      <Campo
        etiqueta="N.º de animales"
        type="number"
        min={1}
        required
        value={nAnimales}
        onChange={(e) => setNAnimales(e.target.value)}
      />
      <Campo
        etiqueta="Peso promedio (kg)"
        type="number"
        min={1}
        required
        value={peso}
        onChange={(e) => setPeso(e.target.value)}
      />
      <Boton type="submit" cargando={enviando} style={{ marginBottom: "1rem" }}>
        Crear lote
      </Boton>
      {error && <p className="campoError" style={{ gridColumn: "1 / -1", color: "var(--rojo-700)" }}>{error}</p>}
    </form>
  );
}
