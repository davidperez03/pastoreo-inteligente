"""Job diario de biomasa: el eslabón que une clima, modelo y Kalman.

Para cada potrero: rehidrata el agregado `EstimacionBiomasa` desde su estado
persistido (biomasa, varianza del Kalman, agua en suelo), aplica el clima del
día (predicción §4) y, si hay lectura NDVI fresca de esa fecha, la corrección
(§5). Persiste el nuevo estado y registra los eventos `BiomasaRecalculada`
en `eventos_dominio` (auditoría §10) además de publicarlos en el bus.

Corre como proceso del sistema (worker), igual que los jobs de clima y NDVI:
sin organización activa — recorre los potreros de todas las fincas.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from srp.agronomia.domain.crecimiento import ParametrosEspecie
from srp.agronomia.domain.estimacion import EstadoSuelo, EstimacionBiomasa
from srp.agronomia.domain.kalman import KalmanBiomasa
from srp.shared.events import BusEventosEnMemoria
from srp.shared.types import LecturaNdvi, RegistroClima

logger = logging.getLogger(__name__)

# Capacidad de campo por textura (mm de agua retenible). Valores de partida
# para los Llanos, calibrables por potrero en fase de piloto.
CAPACIDAD_CAMPO_MM = {"franco": 150.0, "arcilloso": 180.0, "arenoso": 100.0}
CAPACIDAD_CAMPO_DEFAULT_MM = 150.0

# Arranque en frío: sin biomasa previa se parte de un valor conservador de
# pastura en recuperación; el Kalman corrige rápido con las primeras lecturas
# NDVI (varianza inicial alta = poca confianza en este valor).
BIOMASA_INICIAL_KG_MS_HA = 1000.0
VARIANZA_INICIAL = 100.0

# Misma zona horaria que el job de clima: "ayer" debe significar lo mismo en
# ambos jobs o la biomasa buscará un registro que el clima aún no escribió.
ZONA_HORARIA = ZoneInfo("America/Bogota")


def _ayer() -> date:
    return datetime.now(ZONA_HORARIA).date() - timedelta(days=1)


async def recalcular_biomasa_diaria(
    pool: asyncpg.Pool,
    bus: BusEventosEnMemoria | None = None,
    fecha: date | None = None,
) -> dict[str, int]:
    """Recalcula la biomasa de todos los potreros para `fecha` (default: ayer,
    el último día con clima completo). Devuelve conteos {ok, sin_clima, fallidos}.
    Reejecutar con la misma fecha es idempotente sobre el clima (mismo registro)
    aunque avanza el Kalman; el escenario esperado es una corrida por día."""
    fecha = fecha or _ayer()
    filas = await pool.fetch(
        """
        SELECT p.id, p.tipo_suelo, p.factor_fatiga, p.biomasa_actual_kg_ms_ha,
               p.kalman_varianza, p.suelo_mm,
               ST_Y(ST_Centroid(p.geom::geometry)) AS latitud,
               f.estacion_clima_id,
               e.nombre AS especie_nombre, e.temp_base, e.tasa_max_crecimiento,
               e.gdd_optimo_diario, e.dias_descanso_ideal, e.curva_k
        FROM potreros p
        JOIN fincas f ON f.id = p.finca_id
        JOIN especies_pasto e ON e.id = p.especie_pasto_id
        """
    )
    ok = sin_clima = fallidos = 0
    for fila in filas:
        try:
            clima = await _clima_del_dia(pool, fila["estacion_clima_id"], fecha)
            if clima is None:
                sin_clima += 1
                logger.warning(
                    "Potrero %s sin clima para %s (¿corrió el job de clima?); se omite",
                    fila["id"],
                    fecha,
                )
                continue
            estimacion = _rehidratar(fila)
            especie = _especie(fila)
            estimacion.actualizar_con_clima(clima, especie, _estado_suelo(fila))

            lectura = await _ndvi_fresco(pool, fila["id"], fecha)
            if lectura is not None:
                estimacion.corregir_con_ndvi(lectura, especie)

            await _persistir(pool, estimacion)
            await _auditar_y_publicar(pool, bus, estimacion)
            ok += 1
        except Exception:
            fallidos += 1
            logger.exception("Fallo recalculando biomasa del potrero %s", fila["id"])
    logger.info(
        "Job biomasa %s: %d ok, %d sin clima, %d fallidos de %d potreros",
        fecha,
        ok,
        sin_clima,
        fallidos,
        len(filas),
    )
    return {"ok": ok, "sin_clima": sin_clima, "fallidos": fallidos}


async def _clima_del_dia(
    pool: asyncpg.Pool, estacion_id, fecha: date
) -> RegistroClima | None:
    if estacion_id is None:
        return None
    fila = await pool.fetchrow(
        """
        SELECT fecha, temp_media, temp_max, temp_min, precipitacion_mm,
               humedad_suelo_pct, estimado
        FROM registros_clima
        WHERE estacion_clima_id = $1 AND fecha = $2
        """,
        estacion_id,
        fecha,
    )
    if fila is None or fila["temp_media"] is None:
        return None
    return RegistroClima(
        fecha=fila["fecha"],
        temp_media=float(fila["temp_media"]),
        temp_max=float(fila["temp_max"]),
        temp_min=float(fila["temp_min"]),
        precipitacion_mm=float(fila["precipitacion_mm"] or 0.0),
        humedad_suelo_pct=None
        if fila["humedad_suelo_pct"] is None
        else float(fila["humedad_suelo_pct"]),
        estimado=fila["estimado"],
    )


async def _ndvi_fresco(
    pool: asyncpg.Pool, potrero_id, fecha: date
) -> LecturaNdvi | None:
    """Lectura NDVI de la fecha procesada, solo si no es reuso stale (§6)."""
    fila = await pool.fetchrow(
        """
        SELECT fecha, ndvi_promedio, cobertura_nubes_pct, stale, fuente
        FROM lecturas_ndvi
        WHERE potrero_id = $1 AND fecha = $2 AND NOT stale
        """,
        potrero_id,
        fecha,
    )
    if fila is None or fila["ndvi_promedio"] is None:
        return None
    cobertura = float(fila["cobertura_nubes_pct"] or 0.0)
    return LecturaNdvi(
        fecha=fila["fecha"],
        ndvi_promedio=float(fila["ndvi_promedio"]),
        calidad=max(0.05, 1.0 - cobertura / 100.0),
        fuente=fila["fuente"],
        stale=False,
    )


def _rehidratar(fila) -> EstimacionBiomasa:
    biomasa = (
        BIOMASA_INICIAL_KG_MS_HA
        if fila["biomasa_actual_kg_ms_ha"] is None
        else float(fila["biomasa_actual_kg_ms_ha"])
    )
    varianza = (
        VARIANZA_INICIAL
        if fila["kalman_varianza"] is None
        else float(fila["kalman_varianza"])
    )
    capacidad = CAPACIDAD_CAMPO_MM.get(fila["tipo_suelo"], CAPACIDAD_CAMPO_DEFAULT_MM)
    # Arranque en frío del bucket: suelo a media capacidad en vez de seco —
    # menos error esperado en cualquier época que asumir sequía absoluta.
    suelo = capacidad / 2 if fila["suelo_mm"] is None else float(fila["suelo_mm"])
    return EstimacionBiomasa(
        potrero_id=fila["id"],
        kalman=KalmanBiomasa(biomasa, varianza),
        suelo_actual_mm=suelo,
    )


def _especie(fila) -> ParametrosEspecie:
    return ParametrosEspecie(
        nombre=fila["especie_nombre"],
        temp_base=float(fila["temp_base"]),
        tasa_max_crecimiento=float(fila["tasa_max_crecimiento"]),
        gdd_optimo_diario=float(fila["gdd_optimo_diario"]),
        dias_descanso_ideal=int(fila["dias_descanso_ideal"]),
        curva_k=float(fila["curva_k"]),
    )


def _estado_suelo(fila) -> EstadoSuelo:
    return EstadoSuelo(
        capacidad_campo_mm=CAPACIDAD_CAMPO_MM.get(
            fila["tipo_suelo"], CAPACIDAD_CAMPO_DEFAULT_MM
        ),
        tipo_suelo=fila["tipo_suelo"],
        latitud_grados=float(fila["latitud"]),
        factor_fatiga=float(fila["factor_fatiga"]),
    )


async def _persistir(pool: asyncpg.Pool, estimacion: EstimacionBiomasa) -> None:
    await pool.execute(
        """
        UPDATE potreros
        SET biomasa_actual_kg_ms_ha = $2, kalman_varianza = $3, suelo_mm = $4
        WHERE id = $1
        """,
        estimacion.potrero_id,
        estimacion.biomasa_kg_ms_ha,
        estimacion.varianza,
        estimacion.suelo_mm,
    )


async def _auditar_y_publicar(
    pool: asyncpg.Pool,
    bus: BusEventosEnMemoria | None,
    estimacion: EstimacionBiomasa,
) -> None:
    eventos = estimacion.eventos_pendientes()
    for evento in eventos:
        await pool.execute(
            "INSERT INTO eventos_dominio (tipo, payload) VALUES ($1, $2)",
            type(evento).__name__,
            json.dumps(asdict(evento), default=str),
        )
    if bus is not None:
        await bus.publicar(eventos)
    estimacion.limpiar_eventos()
