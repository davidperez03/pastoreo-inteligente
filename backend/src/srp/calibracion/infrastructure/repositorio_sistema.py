"""Repositorio de calibración para procesamiento por eventos (sistema).

Los handlers del bus corren dentro del proceso de la API, reaccionando a un
evento de UNA organización concreta (a diferencia de los jobs del worker, que
sí operan intencionalmente sobre todas). El pool de la API conecta con un rol
sin BYPASSRLS (§10, §19.3): una escritura sin `app.current_org` fijado no
falla con error, simplemente no afecta ninguna fila — silencioso y peor que
un error — así que resolvemos la organización dueña del potrero y pasamos por
`conexion_org` igual que cualquier otra escritura de dominio.
"""

from __future__ import annotations

import asyncpg

from srp.shared.db import conexion_org
from srp.shared.types import PotreroId


class PotreroSinOrganizacion(LookupError):
    """El potrero no resuelve a ninguna organización (borrado entre el
    evento y el handler, o dato inconsistente)."""


class RepositorioCalibracionSistema:
    """Implementa el puerto `RepositorioCalibracion` resolviendo la
    organización del potrero en cada operación."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _organizacion(self, potrero_id: PotreroId):
        # Vía la función SECURITY DEFINER (migración 0004) — ver el mismo
        # razonamiento en EstadoPotreroHandler._organizacion_del_potrero.
        org_id = await self._pool.fetchval(
            "SELECT organizacion_de_potrero($1)", potrero_id
        )
        if org_id is None:
            raise PotreroSinOrganizacion(str(potrero_id))
        return org_id

    async def leer_estado(
        self, potrero_id: PotreroId
    ) -> tuple[float, int, float | None] | None:
        try:
            org_id = await self._organizacion(potrero_id)
        except PotreroSinOrganizacion:
            # Contrato del puerto: potrero inexistente -> None, no excepción
            # (el handler ya maneja ese caso con un log y sin recalibrar).
            return None
        async with conexion_org(self._pool, org_id) as con:
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
        self, potrero_id: PotreroId, factor: float, n_ciclos: int
    ) -> None:
        org_id = await self._organizacion(potrero_id)
        async with conexion_org(self._pool, org_id) as con:
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
