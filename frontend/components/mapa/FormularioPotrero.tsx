"use client";

/** Formulario de metadatos del potrero + envío al backend (POST /potreros/).
 *
 * Guardar `metodo_levantamiento` y `accuracy_m` junto al polígono permite
 * distinguir en calibración si un error viene del modelo agronómico o de una
 * planimetría imprecisa (§3.5 del SRP).
 */

import { useState } from "react";
import type { FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import {
  ESPECIES_PASTO,
  METODOS_LEVANTAMIENTO,
  TIPOS_SUELO,
} from "./tipos";
import type {
  CuerpoCrearPotrero,
  MetodoLevantamiento,
  PuntoLatLng,
  RespuestaPotrero,
  TipoSuelo,
} from "./tipos";
import styles from "./mapa.module.css";

type EstadoEnvio =
  | { tipo: "inicial" }
  | { tipo: "enviando" }
  | { tipo: "exito"; respuesta: RespuestaPotrero }
  | { tipo: "error"; mensaje: string };

export default function FormularioPotrero({
  puntos,
}: {
  puntos: PuntoLatLng[];
}) {
  const [nombre, setNombre] = useState("");
  const [especieId, setEspecieId] = useState<string>(ESPECIES_PASTO[0].id);
  const [tipoSuelo, setTipoSuelo] = useState<TipoSuelo>("franco");
  const [metodo, setMetodo] = useState<MetodoLevantamiento>("gps_celular");
  const [accuracy, setAccuracy] = useState("5");
  // finca_id como texto temporal: en integración vendrá de la sesión/selector.
  const [fincaId, setFincaId] = useState("");
  const [estado, setEstado] = useState<EstadoEnvio>({ tipo: "inicial" });

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (puntos.length < 3) {
      setEstado({
        tipo: "error",
        mensaje: "Se necesitan mínimo 3 puntos para formar el polígono.",
      });
      return;
    }
    const accuracyM = Number(accuracy);
    if (!Number.isFinite(accuracyM) || accuracyM < 0) {
      setEstado({
        tipo: "error",
        mensaje: "La precisión (accuracy_m) debe ser un número mayor o igual a 0.",
      });
      return;
    }
    const cuerpo: CuerpoCrearPotrero = {
      finca_id: fincaId.trim(),
      nombre: nombre.trim(),
      puntos,
      especie_pasto_id: especieId,
      tipo_suelo: tipoSuelo,
      metodo_levantamiento: metodo,
      accuracy_m: accuracyM,
    };
    setEstado({ tipo: "enviando" });
    try {
      const respuesta = await api.post<RespuestaPotrero>("/potreros/", cuerpo);
      setEstado({ tipo: "exito", respuesta });
    } catch (err) {
      if (err instanceof ApiError) {
        setEstado({
          tipo: "error",
          mensaje: `Error ${err.status} del servidor: ${err.message || "sin detalle"}`,
        });
      } else {
        setEstado({
          tipo: "error",
          mensaje:
            "No se pudo contactar el servidor. Verifica la conexión e intenta de nuevo.",
        });
      }
    }
  }

  return (
    <form className={styles.formulario} onSubmit={enviar}>
      <h2>Guardar potrero</h2>
      <label className={styles.campo}>
        Nombre del potrero
        <input
          type="text"
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          required
          placeholder="Ej: La Esperanza 3"
        />
      </label>
      <label className={styles.campo}>
        Especie de pasto
        <select
          value={especieId}
          onChange={(e) => setEspecieId(e.target.value)}
        >
          {ESPECIES_PASTO.map((especie) => (
            <option key={especie.id} value={especie.id}>
              {especie.nombre}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.campo}>
        Tipo de suelo
        <select
          value={tipoSuelo}
          onChange={(e) => setTipoSuelo(e.target.value as TipoSuelo)}
        >
          {TIPOS_SUELO.map((tipo) => (
            <option key={tipo} value={tipo}>
              {tipo}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.campo}>
        Método de levantamiento
        <select
          value={metodo}
          onChange={(e) => setMetodo(e.target.value as MetodoLevantamiento)}
        >
          {METODOS_LEVANTAMIENTO.map((m) => (
            <option key={m.valor} value={m.valor}>
              {m.etiqueta}
            </option>
          ))}
        </select>
      </label>
      <label className={styles.campo}>
        Precisión del levantamiento (m)
        <input
          type="number"
          value={accuracy}
          onChange={(e) => setAccuracy(e.target.value)}
          min="0"
          step="any"
          required
        />
      </label>
      <label className={styles.campo}>
        Finca (id)
        <input
          type="text"
          value={fincaId}
          onChange={(e) => setFincaId(e.target.value)}
          required
          placeholder="Id de la finca (temporal)"
        />
      </label>
      <button
        type="submit"
        className={styles.botonPrimario}
        disabled={estado.tipo === "enviando"}
      >
        {estado.tipo === "enviando" ? "Guardando…" : "Guardar potrero"}
      </button>

      {estado.tipo === "exito" && (
        <div>
          <p className={styles.exito}>
            Potrero guardado correctamente.
            {typeof estado.respuesta.area_ha === "number"
              ? ` Área calculada por el servidor: ${estado.respuesta.area_ha.toFixed(2)} ha.`
              : ""}
          </p>
          {estado.respuesta.advertencia ? (
            <p className={styles.advertencia}>
              Advertencia: {estado.respuesta.advertencia}
            </p>
          ) : null}
        </div>
      )}
      {estado.tipo === "error" && (
        <p className={styles.error} role="alert">
          {estado.mensaje}
        </p>
      )}
    </form>
  );
}
