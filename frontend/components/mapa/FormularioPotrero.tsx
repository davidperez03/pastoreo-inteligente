"use client";

/** Formulario de metadatos del potrero + envío al backend (POST /potreros/).
 *
 * Guardar `metodo_levantamiento` y `accuracy_m` junto al polígono permite
 * distinguir en calibración si un error viene del modelo agronómico o de una
 * planimetría imprecisa (§3.5 del SRP).
 */

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import Boton from "@/components/ui/Boton";
import { Campo, CampoSelect } from "@/components/ui/Campo";
import Tarjeta from "@/components/ui/Tarjeta";
import { ApiError } from "@/lib/api";
import { especiesApi } from "@/lib/fincas";
import { useFincaActual } from "@/lib/finca-actual";
import { potrerosApi, type PotreroApi } from "@/lib/potreros";
import { ESPECIES_PASTO, METODOS_LEVANTAMIENTO, TIPOS_SUELO } from "./tipos";
import type {
  CuerpoCrearPotrero,
  MetodoLevantamiento,
  PuntoLatLng,
  TipoSuelo,
} from "./tipos";
import styles from "./mapa.module.css";

type EstadoEnvio =
  | { tipo: "inicial" }
  | { tipo: "enviando" }
  | { tipo: "exito"; respuesta: PotreroApi }
  | { tipo: "error"; mensaje: string };

/** Solo lo que este formulario necesita renderizar de una especie — evita
 * acoplar el fallback local (tipos.ts) a la forma exacta de la API. */
interface OpcionEspecie {
  id: string;
  nombre: string;
}

export default function FormularioPotrero({ puntos }: { puntos: PuntoLatLng[] }) {
  const { fincaId, finca } = useFincaActual();
  const [especies, setEspecies] = useState<OpcionEspecie[]>([...ESPECIES_PASTO]);
  const [nombre, setNombre] = useState("");
  const [especieId, setEspecieId] = useState<string>(ESPECIES_PASTO[0].id);
  const [tipoSuelo, setTipoSuelo] = useState<TipoSuelo>("franco");
  const [metodo, setMetodo] = useState<MetodoLevantamiento>("gps_celular");
  const [accuracy, setAccuracy] = useState("5");
  const [estado, setEstado] = useState<EstadoEnvio>({ tipo: "inicial" });

  useEffect(() => {
    especiesApi
      .listar()
      .then((lista) => {
        if (lista.length > 0) {
          setEspecies(lista);
          setEspecieId(lista[0].id);
        }
      })
      .catch(() => {
        /* deja las especies hardcodeadas como fallback */
      });
  }, []);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (!fincaId) {
      setEstado({ tipo: "error", mensaje: "Elige o crea una finca antes de guardar." });
      return;
    }
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
      finca_id: fincaId,
      nombre: nombre.trim(),
      puntos,
      especie_pasto_id: especieId,
      tipo_suelo: tipoSuelo,
      metodo_levantamiento: metodo,
      accuracy_m: accuracyM,
    };
    setEstado({ tipo: "enviando" });
    try {
      const respuesta = await potrerosApi.crear(cuerpo);
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
    <Tarjeta as="form" onSubmit={enviar} className={styles.formulario}>
      <h2>Guardar potrero</h2>

      <p style={{ fontSize: "0.85rem", color: "var(--texto-tenue)", marginBottom: "1rem" }}>
        Finca: <strong>{finca?.nombre ?? "ninguna seleccionada"}</strong>{" "}
        {!fincaId && <a href="/fincas">— crear una</a>}
      </p>

      <Campo
        etiqueta="Nombre del potrero"
        value={nombre}
        onChange={(e) => setNombre(e.target.value)}
        required
        placeholder="Ej: La Esperanza 3"
      />
      <CampoSelect
        etiqueta="Especie de pasto"
        value={especieId}
        onChange={(e) => setEspecieId(e.target.value)}
      >
        {especies.map((especie) => (
          <option key={especie.id} value={especie.id}>
            {especie.nombre}
          </option>
        ))}
      </CampoSelect>
      <CampoSelect
        etiqueta="Tipo de suelo"
        value={tipoSuelo}
        onChange={(e) => setTipoSuelo(e.target.value as TipoSuelo)}
      >
        {TIPOS_SUELO.map((tipo) => (
          <option key={tipo} value={tipo}>
            {tipo}
          </option>
        ))}
      </CampoSelect>
      <CampoSelect
        etiqueta="Método de levantamiento"
        value={metodo}
        onChange={(e) => setMetodo(e.target.value as MetodoLevantamiento)}
      >
        {METODOS_LEVANTAMIENTO.map((m) => (
          <option key={m.valor} value={m.valor}>
            {m.etiqueta}
          </option>
        ))}
      </CampoSelect>
      <Campo
        etiqueta="Precisión del levantamiento (m)"
        type="number"
        value={accuracy}
        onChange={(e) => setAccuracy(e.target.value)}
        min="0"
        step="any"
        required
      />

      <Boton type="submit" cargando={estado.tipo === "enviando"} style={{ width: "100%" }}>
        Guardar potrero
      </Boton>

      {estado.tipo === "exito" && (
        <div style={{ marginTop: "1rem" }}>
          <p className={styles.exito}>
            Potrero guardado correctamente.
            {typeof estado.respuesta.area_ha === "number"
              ? ` Área calculada por el servidor: ${estado.respuesta.area_ha.toFixed(2)} ha.`
              : ""}
          </p>
          {estado.respuesta.advertencia ? (
            <p className={styles.advertencia}>Advertencia: {estado.respuesta.advertencia}</p>
          ) : null}
        </div>
      )}
      {estado.tipo === "error" && (
        <p className={styles.error} role="alert">
          {estado.mensaje}
        </p>
      )}
    </Tarjeta>
  );
}
