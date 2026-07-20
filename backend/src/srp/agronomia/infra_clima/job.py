"""Job diario de sincronización de clima (contexto Agronómico, §11).

Recorre las estaciones de clima asignadas a fincas, obtiene el clima de ayer
del proveedor (con fallback de último-conocido) y lo persiste de forma
idempotente. `crear_scheduler` arma el AsyncIOScheduler con el cron diario de
las 05:00 America/Bogota pero NO lo arranca — eso lo decide el proceso host.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from srp.agronomia.infra_clima.fallback import SinDatosClima, clima_con_fallback
from srp.agronomia.infra_clima.open_meteo import OpenMeteoClimaAdapter
from srp.agronomia.infra_clima.repositorio_clima import guardar_registros
from srp.shared.ports import ProveedorClima
from srp.shared.types import Coordenada

logger = logging.getLogger(__name__)

ZONA_HORARIA = ZoneInfo("America/Bogota")

# Estaciones asignadas a al menos una finca, con sus coordenadas WGS84.
# ubicacion es GEOGRAPHY(POINT): ST_X/ST_Y requieren castearlo a geometry.
_SQL_ESTACIONES_CON_FINCA = """
SELECT DISTINCT
    f.estacion_clima_id,
    ST_Y(e.ubicacion::geometry) AS lat,
    ST_X(e.ubicacion::geometry) AS lng
FROM fincas f
JOIN estaciones_clima e ON e.id = f.estacion_clima_id
WHERE f.estacion_clima_id IS NOT NULL
  AND e.ubicacion IS NOT NULL
"""


def _ayer() -> date:
    return datetime.now(ZONA_HORARIA).date() - timedelta(days=1)


async def sincronizar_clima_diario(
    pool: asyncpg.Pool,
    proveedor: ProveedorClima,
    fecha: date | None = None,
) -> int:
    """Sincroniza el clima de ayer (o `fecha`) para toda estación con finca.

    Idempotente: reejecutarlo el mismo día actualiza las filas existentes en
    vez de duplicarlas (§11). Un fallo en una estación no detiene las demás.
    Devuelve el número de estaciones sincronizadas con éxito.
    """
    fecha_objetivo = fecha or _ayer()
    estaciones = await pool.fetch(_SQL_ESTACIONES_CON_FINCA)
    sincronizadas = 0
    for estacion in estaciones:
        estacion_id = estacion["estacion_clima_id"]
        ubicacion = Coordenada(lat=estacion["lat"], lng=estacion["lng"])
        try:
            registro = await clima_con_fallback(
                proveedor, pool, estacion_id, ubicacion, fecha_objetivo
            )
            await guardar_registros(pool, estacion_id, [registro])
            sincronizadas += 1
        except SinDatosClima:
            logger.exception(
                "Job de clima sin dato para la estación %s en %s "
                "(proveedor caído y sin histórico)",
                estacion_id,
                fecha_objetivo.isoformat(),
            )
    logger.info(
        "Job de clima: %d/%d estaciones sincronizadas para %s",
        sincronizadas,
        len(estaciones),
        fecha_objetivo.isoformat(),
    )
    return sincronizadas


def crear_scheduler(
    pool: asyncpg.Pool, proveedor: ProveedorClima | None = None
) -> AsyncIOScheduler:
    """Scheduler con el cron diario de clima (05:00 America/Bogota).

    No lo arranca: el proceso host debe llamar `scheduler.start()` dentro de un
    event loop en ejecución.
    """
    proveedor_clima = proveedor if proveedor is not None else OpenMeteoClimaAdapter()
    scheduler = AsyncIOScheduler(timezone=ZONA_HORARIA)
    scheduler.add_job(
        sincronizar_clima_diario,
        CronTrigger(hour=5, minute=0, timezone=ZONA_HORARIA),
        args=(pool, proveedor_clima),
        id="sincronizar_clima_diario",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
