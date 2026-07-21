"""Repositorio de calibración para procesamiento por eventos (sistema).

Los handlers del bus corren fuera del ciclo request/response: no hay token ni
organización activa que propagar a la RLS. Este adaptador ejecuta las mismas
consultas que `repositorio_calibracion` pero como proceso interno del sistema
(igual que los jobs de clima/NDVI), confiando en que el `potrero_id` proviene
de un evento de dominio ya autorizado en su origen.
"""

from __future__ import annotations

import asyncpg

from srp.shared.types import PotreroId


class RepositorioCalibracionSistema:
    """Implementa el puerto `RepositorioCalibracion` sin contexto de organización."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def leer_estado(
        self, potrero_id: PotreroId
    ) -> tuple[float, int, float | None] | None:
        fila = await self._pool.fetchrow(
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
        self, potrero_id: PotreroId, factor: float, n_ciclos: int
    ) -> None:
        await self._pool.execute(
            """
            UPDATE potreros
            SET factor_fatiga = $2::double precision, n_ciclos_observados = $3
            WHERE id = $1
            """,
            potrero_id,
            factor,
            n_ciclos,
        )
