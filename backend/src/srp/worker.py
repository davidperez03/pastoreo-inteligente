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
    """Construye el adaptador CDSE si hay credenciales completas.

    Requiere el client OAuth del catálogo (SRP_CDSE_CLIENT_ID/SECRET) y las
    llaves S3 de eodata (SRP_CDSE_S3_ACCESS_KEY/SECRET_KEY); sin cualquiera
    de los dos pares, el job semanal no se programa."""
    if not (
        os.environ.get("SRP_CDSE_CLIENT_ID") and os.environ.get("SRP_CDSE_CLIENT_SECRET")
    ):
        return None
    from srp.agronomia.infra_ndvi.adapter import CopernicusNdviAdapter
    from srp.agronomia.infra_ndvi.cdse_auth import CdseAuth
    from srp.agronomia.infra_ndvi.cdse_catalogo import CatalogoCdse
    from srp.agronomia.infra_ndvi.descarga_s3 import crear_desde_env

    descargador = crear_desde_env()
    if descargador is None:
        logger.warning(
            "Client OAuth CDSE presente pero faltan las llaves S3 "
            "(SRP_CDSE_S3_ACCESS_KEY/SECRET_KEY): job NDVI no programado"
        )
        return None
    return CopernicusNdviAdapter(CatalogoCdse(CdseAuth()), descargador, pool)


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
                "Adaptador NDVI no disponible (ver credenciales CDSE): "
                "job semanal no programado"
            )
        scheduler.start()
        logger.info("Worker SRP iniciado; jobs: %s", [j.id for j in scheduler.get_jobs()])
        await asyncio.Event().wait()  # corre hasta señal externa
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
