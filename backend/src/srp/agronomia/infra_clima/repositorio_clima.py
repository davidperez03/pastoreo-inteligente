"""Persistencia de registros de clima sobre `registros_clima` (§2).

El upsert es idempotente vía el UNIQUE (estacion_clima_id, fecha) del esquema:
un reintento del job diario actualiza la fila existente en vez de duplicarla
(§11, "Idempotencia de jobs").
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import asyncpg

from srp.shared.types import RegistroClima

_SQL_UPSERT = """
INSERT INTO registros_clima (
    estacion_clima_id, fecha, temp_media, temp_max, temp_min,
    precipitacion_mm, humedad_suelo_pct, estimado
) VALUES (
    $1, $2, $3::float8, $4::float8, $5::float8, $6::float8, $7::float8, $8
)
ON CONFLICT (estacion_clima_id, fecha) DO UPDATE SET
    temp_media = EXCLUDED.temp_media,
    temp_max = EXCLUDED.temp_max,
    temp_min = EXCLUDED.temp_min,
    precipitacion_mm = EXCLUDED.precipitacion_mm,
    humedad_suelo_pct = EXCLUDED.humedad_suelo_pct,
    estimado = EXCLUDED.estimado
"""

_SQL_ULTIMO = """
SELECT fecha, temp_media, temp_max, temp_min, precipitacion_mm,
       humedad_suelo_pct, estimado
FROM registros_clima
WHERE estacion_clima_id = $1
ORDER BY fecha DESC
LIMIT 1
"""


async def guardar_registros(
    pool: asyncpg.Pool,
    estacion_id: uuid.UUID,
    registros: Sequence[RegistroClima],
) -> None:
    """Upsert idempotente de registros para una estación (§11)."""
    if not registros:
        return
    filas = [
        (
            estacion_id,
            r.fecha,
            r.temp_media,
            r.temp_max,
            r.temp_min,
            r.precipitacion_mm,
            r.humedad_suelo_pct,
            r.estimado,
        )
        for r in registros
    ]
    async with pool.acquire() as con:
        await con.executemany(_SQL_UPSERT, filas)


async def ultimo_registro(
    pool: asyncpg.Pool, estacion_id: uuid.UUID
) -> RegistroClima | None:
    """Último registro conocido de la estación (el de fecha más reciente)."""
    fila = await pool.fetchrow(_SQL_ULTIMO, estacion_id)
    if fila is None:
        return None
    return RegistroClima(
        fecha=fila["fecha"],
        temp_media=float(fila["temp_media"]),
        temp_max=float(fila["temp_max"]),
        temp_min=float(fila["temp_min"]),
        precipitacion_mm=float(fila["precipitacion_mm"]),
        humedad_suelo_pct=(
            float(fila["humedad_suelo_pct"])
            if fila["humedad_suelo_pct"] is not None
            else None
        ),
        estimado=fila["estimado"],
    )
