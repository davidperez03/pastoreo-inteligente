"""Job semanal de sincronización NDVI (§6, §11).

Recorre todos los potreros, pide el NDVI de la fecha actual al adaptador y
persiste la lectura de forma idempotente (reejecutar el job no duplica filas).
Un potrero sin dato no aborta el job completo: se registra y se continúa.

El scheduler (domingos 03:00 América/Bogotá) se construye pero NO se arranca
aquí — el proceso dueño del ciclo de vida (app/worker) llama `.start()`.
"""

from __future__ import annotations

import json
import logging
from datetime import date

import asyncpg
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from srp.agronomia.infra_ndvi.adapter import NdviNoDisponibleError
from srp.agronomia.infra_ndvi.repositorio_ndvi import guardar_lectura
from srp.shared.ports import ProveedorNdvi

logger = logging.getLogger(__name__)


async def sincronizar_ndvi_semanal(
    pool: asyncpg.Pool,
    adapter: ProveedorNdvi,
    fecha: date | None = None,
) -> dict[str, int]:
    """Sincroniza el NDVI de todos los potreros. Devuelve conteos {ok, fallidos}."""
    fecha = fecha or date.today()
    filas = await pool.fetch(
        "SELECT id, ST_AsGeoJSON(geom::geometry) AS geojson FROM potreros"
    )
    ok = 0
    fallidos = 0
    for fila in filas:
        potrero_id = fila["id"]
        try:
            lectura = await adapter.obtener_ndvi(json.loads(fila["geojson"]), fecha)
            await guardar_lectura(pool, potrero_id, lectura)
            ok += 1
        except NdviNoDisponibleError as exc:
            # §11: un potrero sin dato ni fallback no tumba el job completo.
            fallidos += 1
            logger.error(
                "NDVI no disponible para potrero %s: %s", potrero_id, exc
            )
        except Exception:
            fallidos += 1
            logger.exception(
                "Fallo inesperado sincronizando NDVI del potrero %s", potrero_id
            )
    logger.info(
        "Job NDVI semanal terminado: %d ok, %d fallidos de %d potreros",
        ok,
        fallidos,
        len(filas),
    )
    return {"ok": ok, "fallidos": fallidos}


def crear_scheduler_ndvi(
    pool: asyncpg.Pool, adapter: ProveedorNdvi
) -> AsyncIOScheduler:
    """Scheduler semanal (domingos 03:00 America/Bogota), sin arrancar."""
    scheduler = AsyncIOScheduler(timezone="America/Bogota")
    scheduler.add_job(
        sincronizar_ndvi_semanal,
        CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="America/Bogota"),
        args=[pool, adapter],
        id="sincronizar_ndvi_semanal",
        replace_existing=True,
        coalesce=True,  # si el worker estuvo caído, una sola corrida de recuperación
        misfire_grace_time=3600,
    )
    return scheduler
