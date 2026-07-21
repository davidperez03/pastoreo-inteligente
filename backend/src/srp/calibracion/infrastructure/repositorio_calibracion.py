"""Repositorio Postgres del contexto Calibración.

Solo lee y escribe las columnas de `potreros` que este contexto posee
funcionalmente: `factor_fatiga` y `n_ciclos_observados` (escritura EXCLUSIVA de
Calibración, §17.1). Lee `biomasa_actual_kg_ms_ha` como predicción vigente para
comparar contra la medición real. Todo acceso pasa por `conexion_org` para
respetar la RLS multi-tenant (§2, §10).
"""

from __future__ import annotations

import asyncpg

from srp.shared.db import conexion_org
from srp.shared.types import OrganizacionId, PotreroId


class RepositorioCalibracionPg:
    """Adaptador que implementa el puerto `RepositorioCalibracion`.

    Se construye con el pool y la organización activa; así el handler puede
    tratarlo como un repositorio simple (`leer_estado`/`guardar_estado` por
    potrero) sin conocer detalles de conexión ni de tenancy.
    """

    def __init__(self, pool: asyncpg.Pool, org_id: OrganizacionId) -> None:
        self._pool = pool
        self._org_id = org_id

    async def leer_estado(
        self, potrero_id: PotreroId
    ) -> tuple[float, int, float | None] | None:
        return await leer_estado(self._pool, self._org_id, potrero_id)

    async def guardar_estado(
        self, potrero_id: PotreroId, factor: float, n_ciclos: int
    ) -> None:
        await guardar_estado(self._pool, self._org_id, potrero_id, factor, n_ciclos)


async def leer_estado(
    pool: asyncpg.Pool, org_id: OrganizacionId, potrero_id: PotreroId
) -> tuple[float, int, float | None] | None:
    """Devuelve `(factor_fatiga, n_ciclos_observados, biomasa_predicha)`.

    `biomasa_predicha` es `potreros.biomasa_actual_kg_ms_ha` (la predicción
    vigente). Devuelve `None` si el potrero no existe (o la RLS lo oculta).
    """
    async with conexion_org(pool, org_id) as con:
        fila = await con.fetchrow(
            """
            SELECT factor_fatiga, n_ciclos_observados, biomasa_actual_kg_ms_ha
            FROM potreros
            WHERE id = $1
            """,
            potrero_id,
        )
    if fila is None:
        return None
    return (
        float(fila["factor_fatiga"]),
        int(fila["n_ciclos_observados"]),
        None
        if fila["biomasa_actual_kg_ms_ha"] is None
        else float(fila["biomasa_actual_kg_ms_ha"]),
    )


async def guardar_estado(
    pool: asyncpg.Pool,
    org_id: OrganizacionId,
    potrero_id: PotreroId,
    factor: float,
    n_ciclos: int,
) -> None:
    """Persiste el nuevo factor de fatiga y contador de ciclos del potrero.

    Escritura EXCLUSIVA del contexto Calibración sobre estas dos columnas
    (§17.1). No toca ninguna otra columna de `potreros`.
    """
    async with conexion_org(pool, org_id) as con:
        await con.execute(
            """
            UPDATE potreros
            SET factor_fatiga = $2::double precision, n_ciclos_observados = $3
            WHERE id = $1
            """,
            potrero_id,
            factor,
            n_ciclos,
        )
