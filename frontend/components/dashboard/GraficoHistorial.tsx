import type { PuntoHistorial } from "./tipos";
import styles from "./dashboard.module.css";

/** Gráfico SVG hecho a mano (sin librerías): serie de biomasa del modelo
 * (línea continua azul) vs. lecturas NDVI satelitales (puntos naranja) con
 * marcas verticales en los eventos reales de entrada/salida de ganado.
 * Es la pieza de explicabilidad de §16: cuando modelo, satélite y manejo
 * real coinciden, el ganadero puede confiar en la sugerencia.
 * Responsive vía viewBox; tooltips con <title> nativo de SVG. */

const ANCHO = 720;
const ALTO = 340;
const MARGEN = { superior: 22, derecho: 14, inferior: 44, izquierdo: 58 };

const COLOR_MODELO = "#2a78d6"; // serie 1 (validada CVD junto a la 2)
const COLOR_NDVI = "#eb6834"; // serie 2
const COLOR_EVENTO = "#898781";
const COLOR_GRILLA = "#e1e0d9";
const COLOR_EJE = "#c3c2b7";
const COLOR_TEXTO = "#898781";

function pasoBonito(bruto: number): number {
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const f = bruto / potencia;
  if (f <= 1) return potencia;
  if (f <= 2) return 2 * potencia;
  if (f <= 2.5) return 2.5 * potencia;
  if (f <= 5) return 5 * potencia;
  return 10 * potencia;
}

const FORMATO_FECHA = new Intl.DateTimeFormat("es-CO", {
  day: "numeric",
  month: "short",
});

function formatearFecha(fechaIso: string): string {
  const [anio, mes, dia] = fechaIso.split("-").map(Number);
  if (!anio || !mes || !dia) return fechaIso;
  return FORMATO_FECHA.format(new Date(anio, mes - 1, dia));
}

function formatearKg(valor: number): string {
  return valor.toLocaleString("es-CO");
}

export default function GraficoHistorial({ puntos }: { puntos: PuntoHistorial[] }) {
  if (puntos.length === 0) {
    return <p className={styles.vacio}>Sin datos de historial para este potrero.</p>;
  }

  const valores = puntos.flatMap((p) =>
    [p.biomasa_modelo, p.biomasa_ndvi].filter((v): v is number => v !== null),
  );
  const minValor = valores.length > 0 ? Math.min(...valores) : 0;
  const maxValor = valores.length > 0 ? Math.max(...valores) : 1;
  const holgura = Math.max((maxValor - minValor) * 0.08, 50);
  const yMin = Math.max(0, minValor - holgura);
  const yMax = maxValor + holgura;

  const anchoUtil = ANCHO - MARGEN.izquierdo - MARGEN.derecho;
  const altoUtil = ALTO - MARGEN.superior - MARGEN.inferior;
  const x = (i: number): number =>
    MARGEN.izquierdo +
    (puntos.length > 1 ? (i / (puntos.length - 1)) * anchoUtil : anchoUtil / 2);
  const y = (v: number): number =>
    MARGEN.superior + altoUtil - ((v - yMin) / (yMax - yMin)) * altoUtil;

  // Ticks del eje Y (valores "bonitos" dentro del dominio).
  const pasoY = pasoBonito((yMax - yMin) / 4);
  const ticksY: number[] = [];
  for (
    let n = Math.ceil(yMin / pasoY);
    n * pasoY <= yMax;
    n++
  ) {
    // Multiplicar el índice entero evita acumular error de coma flotante.
    ticksY.push(Math.round(n * pasoY));
  }

  // Ticks del eje X: ~6 etiquetas de fecha repartidas.
  const pasoX = Math.max(1, Math.ceil(puntos.length / 6));
  const ticksX = puntos
    .map((p, i) => ({ punto: p, i }))
    .filter(({ i }) => i % pasoX === 0 || i === puntos.length - 1);

  // Línea del modelo: segmentos separados donde haya nulls.
  const segmentos: string[] = [];
  let segmento: string[] = [];
  puntos.forEach((p, i) => {
    if (p.biomasa_modelo === null) {
      if (segmento.length > 1) segmentos.push(segmento.join(" "));
      segmento = [];
    } else {
      segmento.push(
        `${segmento.length === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.biomasa_modelo).toFixed(1)}`,
      );
    }
  });
  if (segmento.length > 1) segmentos.push(segmento.join(" "));

  const eventos = puntos
    .map((p, i) => ({ punto: p, i }))
    .filter(({ punto }) => punto.evento !== null);
  const lecturasNdvi = puntos
    .map((p, i) => ({ punto: p, i }))
    .filter(({ punto }) => punto.biomasa_ndvi !== null);

  const yBase = MARGEN.superior + altoUtil;
  const anchoColumna = puntos.length > 1 ? anchoUtil / (puntos.length - 1) : anchoUtil;

  return (
    <figure className={styles.panelGrafico}>
      <div className={styles.leyenda} aria-hidden="true">
        <span className={styles.leyendaItem}>
          <svg width="22" height="10" viewBox="0 0 22 10">
            <line x1="0" y1="5" x2="22" y2="5" stroke={COLOR_MODELO} strokeWidth="2" />
          </svg>
          Biomasa (modelo agronómico)
        </span>
        <span className={styles.leyendaItem}>
          <svg width="12" height="12" viewBox="0 0 12 12">
            <circle cx="6" cy="6" r="4" fill={COLOR_NDVI} stroke="#fcfcfb" strokeWidth="1.5" />
          </svg>
          Biomasa (NDVI satelital)
        </span>
        <span className={styles.leyendaItem}>
          <svg width="12" height="14" viewBox="0 0 12 14">
            <line x1="6" y1="0" x2="6" y2="14" stroke={COLOR_EVENTO} strokeWidth="1.5" strokeDasharray="3 3" />
          </svg>
          Evento real (E entrada · S salida)
        </span>
      </div>

      <svg
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        className={styles.svgGrafico}
        role="img"
        aria-label="Serie temporal de biomasa: modelo agronómico frente a lecturas NDVI y eventos de entrada y salida de ganado"
      >
        {/* Grilla y eje Y */}
        {ticksY.map((v) => (
          <g key={`ty-${v}`}>
            <line
              x1={MARGEN.izquierdo}
              y1={y(v)}
              x2={ANCHO - MARGEN.derecho}
              y2={y(v)}
              stroke={COLOR_GRILLA}
              strokeWidth="1"
            />
            <text
              x={MARGEN.izquierdo - 8}
              y={y(v) + 3.5}
              textAnchor="end"
              fontSize="11"
              fill={COLOR_TEXTO}
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {formatearKg(v)}
            </text>
          </g>
        ))}
        <text x={MARGEN.izquierdo - 8} y={12} textAnchor="end" fontSize="10" fill={COLOR_TEXTO}>
          kg MS/ha
        </text>

        {/* Eje X */}
        <line
          x1={MARGEN.izquierdo}
          y1={yBase}
          x2={ANCHO - MARGEN.derecho}
          y2={yBase}
          stroke={COLOR_EJE}
          strokeWidth="1"
        />
        {ticksX.map(({ punto, i }) => (
          <text
            key={`tx-${punto.fecha}`}
            x={x(i)}
            y={yBase + 18}
            textAnchor="middle"
            fontSize="11"
            fill={COLOR_TEXTO}
          >
            {formatearFecha(punto.fecha)}
          </text>
        ))}

        {/* Marcas verticales de eventos entrada/salida */}
        {eventos.map(({ punto, i }) => (
          <g key={`ev-${punto.fecha}`}>
            <line
              x1={x(i)}
              y1={MARGEN.superior}
              x2={x(i)}
              y2={yBase}
              stroke={COLOR_EVENTO}
              strokeWidth="1.5"
              strokeDasharray="3 3"
            />
            <text
              x={x(i)}
              y={MARGEN.superior - 6}
              textAnchor="middle"
              fontSize="10"
              fontWeight="600"
              fill="#52514e"
            >
              {punto.evento === "entrada" ? "E" : "S"}
            </text>
            <title>
              {`${punto.evento === "entrada" ? "Entrada" : "Salida"} de ganado — ${formatearFecha(punto.fecha)}`}
            </title>
          </g>
        ))}

        {/* Serie del modelo (línea continua) */}
        {segmentos.map((d) => (
          <path key={d} d={d} fill="none" stroke={COLOR_MODELO} strokeWidth="2" />
        ))}

        {/* Lecturas NDVI (puntos discretos, con anillo de superficie) */}
        {lecturasNdvi.map(({ punto, i }) => (
          <circle
            key={`ndvi-${punto.fecha}`}
            cx={x(i)}
            cy={y(punto.biomasa_ndvi as number)}
            r="4"
            fill={COLOR_NDVI}
            stroke="#fcfcfb"
            strokeWidth="1.5"
          >
            <title>
              {`NDVI ${formatearFecha(punto.fecha)}: ${formatearKg(punto.biomasa_ndvi as number)} kg MS/ha`}
            </title>
          </circle>
        ))}

        {/* Columnas invisibles de hover: tooltip por día */}
        {puntos.map((p, i) => (
          <rect
            key={`hover-${p.fecha}`}
            x={x(i) - anchoColumna / 2}
            y={MARGEN.superior}
            width={anchoColumna}
            height={altoUtil}
            fill="transparent"
          >
            <title>
              {[
                formatearFecha(p.fecha),
                p.biomasa_modelo !== null
                  ? `Modelo: ${formatearKg(p.biomasa_modelo)} kg MS/ha`
                  : "Modelo: sin dato",
                p.biomasa_ndvi !== null
                  ? `NDVI: ${formatearKg(p.biomasa_ndvi)} kg MS/ha`
                  : null,
                p.evento !== null
                  ? `Evento: ${p.evento === "entrada" ? "entrada" : "salida"} de ganado`
                  : null,
              ]
                .filter((linea): linea is string => linea !== null)
                .join("\n")}
            </title>
          </rect>
        ))}
      </svg>
    </figure>
  );
}
