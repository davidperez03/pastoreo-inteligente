"""Worker de jobs programados del SRP (§19.2: proceso separado de la API).

Programa:
- 05:00 America/Bogota — clima diario (Open-Meteo → registros_clima)
- 05:30 America/Bogota — biomasa diaria (modelo + Kalman → potreros)
- dom 03:00 America/Bogota — NDVI semanal (CDSE → lecturas_ndvi), solo si hay
  credenciales SRP_CDSE_CLIENT_ID/SECRET en el entorno.

Uso:
    python -m srp.worker            # scheduler en primer plano
    python -m srp.worker --una-vez  # ejecuta clima+biomasa una vez y termina
                                    # (útil para cron externo o smoke tests)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from srp.agronomia.application.recalcular_biomasa import recalcular_biomasa_diaria
from srp.agronomia.infra_clima.job import sincronizar_clima_diario
from srp.agronomia.infra_clima.open_meteo import OpenMeteoClimaAdapter
from srp.shared.db import crear_pool

logger = logging.getLogger(__name__)
TZ = ZoneInfo("America/Bogota")


def _adapter_ndvi(pool):
    """Construye el adaptador CDSE cuando esté completa la descarga de bandas.

    El catálogo y el cálculo de NDVI ya existen (infra_ndvi), pero la descarga
    real desde el bucket S3 `eodata` del CDSE requiere credenciales y está
    pendiente; hasta implementarla, el job semanal no se programa (arrancarlo
    solo produciría fallos por potrero al no poder descargar escenas)."""
    if not (
        os.environ.get("SRP_CDSE_CLIENT_ID") and os.environ.get("SRP_CDSE_CLIENT_SECRET")
    ):
        return None
    logger.warning(
        "Credenciales CDSE presentes pero la descarga S3 de bandas aún no está "
        "implementada; el job NDVI queda sin programar"
    )
    return None


async def _ciclo_una_vez(pool) -> None:
    clima = OpenMeteoClimaAdapter()
    resultado_clima = await sincronizar_clima_diario(pool, clima)
    logger.info("Clima: %s", resultado_clima)
    resultado_biomasa = await recalcular_biomasa_diaria(pool)
    logger.info("Biomasa: %s", resultado_biomasa)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"ts":"%(asctime)s","nivel":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
    )
    pool = await crear_pool()
    try:
        if "--una-vez" in sys.argv:
            await _ciclo_una_vez(pool)
            return

        scheduler = AsyncIOScheduler(timezone=TZ)
        clima = OpenMeteoClimaAdapter()
        scheduler.add_job(
            sincronizar_clima_diario,
            CronTrigger(hour=5, minute=0, timezone=TZ),
            args=[pool, clima],
            id="clima_diario",
        )
        scheduler.add_job(
            recalcular_biomasa_diaria,
            CronTrigger(hour=5, minute=30, timezone=TZ),
            args=[pool],
            id="biomasa_diaria",
        )
        ndvi = _adapter_ndvi(pool)
        if ndvi is not None:
            from srp.agronomia.infra_ndvi.job import sincronizar_ndvi_semanal

            scheduler.add_job(
                sincronizar_ndvi_semanal,
                CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=TZ),
                args=[pool, ndvi],
                id="ndvi_semanal",
            )
        else:
            logger.warning(
                "Sin credenciales CDSE (SRP_CDSE_CLIENT_ID/SECRET): job NDVI no programado"
            )
        scheduler.start()
        logger.info("Worker SRP iniciado; jobs: %s", [j.id for j in scheduler.get_jobs()])
        await asyncio.Event().wait()  # corre hasta señal externa
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
