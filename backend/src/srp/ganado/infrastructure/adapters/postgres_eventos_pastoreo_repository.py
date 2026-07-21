"""Adaptador de salida: EventosPastoreoRepository sobre Postgres."""

from __future__ import annotations

import uuid
from datetime import date

import asyncpg

from srp.ganado.domain.entities import EventoPastoreo
from srp.ganado.domain.ports.eventos_pastoreo_repository import EventosPastoreoRepository
from srp.shared.db import conexion_org
from srp.shared.types import LoteId, PotreroId

_COLUMNAS = "id, lote_id, potrero_id, fecha_entrada, fecha_salida, biomasa_inicial, biomasa_final"


def _a_entidad(fila: asyncpg.Record) -> EventoPastoreo:
    return EventoPastoreo(
        id=fila["id"],
        lote_id=LoteId(fila["lote_id"]),
        potrero_id=PotreroId(fila["potrero_id"]),
        fecha_entrada=fila["fecha_entrada"],
        fecha_salida=fila["fecha_salida"],
        biomasa_inicial=(
            float(fila["biomasa_inicial"]) if fila["biomasa_inicial"] is not None else None
        ),
        biomasa_final=(
            float(fila["biomasa_final"]) if fila["biomasa_final"] is not None else None
        ),
    )


class PostgresEventosPastoreoRepository(EventosPastoreoRepository):
    def __init__(self, pool: asyncpg.Pool, organizacion_id: uuid.UUID) -> None:
        self._pool = pool
        self._organizacion_id = organizacion_id

    async def abrir_evento(
        self,
        lote_id: LoteId,
        potrero_id: PotreroId,
        fecha_entrada: date,
        biomasa_inicial: float | None,
    ) -> EventoPastoreo:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            fila = await con.fetchrow(
                f"""
                INSERT INTO eventos_pastoreo
                  (lote_id, potrero_id, fecha_entrada, biomasa_inicial)
                VALUES ($1, $2, $3, $4)
                RETURNING {_COLUMNAS}
                """,
                lote_id,
                potrero_id,
                fecha_entrada,
                biomasa_inicial,
            )
        return _a_entidad(fila)

    async def cerrar_evento(
        self,
        evento_id: uuid.UUID,
        fecha_salida: date,
        biomasa_final: float | None,
    ) -> EventoPastoreo:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            fila = await con.fetchrow(
                f"""
                UPDATE eventos_pastoreo
                SET fecha_salida = $2, biomasa_final = $3
                WHERE id = $1
                RETURNING {_COLUMNAS}
                """,
                evento_id,
                fecha_salida,
                biomasa_final,
            )
        if fila is None:
            raise LookupError(f"Evento de pastoreo {evento_id} no encontrado")
        return _a_entidad(fila)

    async def evento_abierto_de_lote(self, lote_id: LoteId) -> EventoPastoreo | None:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            fila = await con.fetchrow(
                f"""
                SELECT {_COLUMNAS} FROM eventos_pastoreo
                WHERE lote_id = $1 AND fecha_salida IS NULL
                ORDER BY fecha_entrada DESC
                LIMIT 1
                """,
                lote_id,
            )
        return _a_entidad(fila) if fila else None
