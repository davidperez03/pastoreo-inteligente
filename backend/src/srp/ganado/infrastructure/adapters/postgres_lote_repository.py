"""Adaptador de salida: LoteRepository sobre Postgres (asyncpg + RLS)."""

from __future__ import annotations

import uuid

import asyncpg

from srp.ganado.domain.entities import LoteGanado
from srp.ganado.domain.ports.lote_repository import LoteRepository
from srp.shared.db import conexion_org
from srp.shared.types import FincaId, LoteId

# La biomasa inicial del ciclo en curso vive en la fila abierta de
# eventos_pastoreo (misma tabla de ESTE contexto, no hay cruce de frontera).
_SELECT = """
SELECT l.id, l.finca_id, l.nombre, l.n_animales, l.peso_promedio_kg,
       l.potrero_actual_id,
       (SELECT e.biomasa_inicial FROM eventos_pastoreo e
         WHERE e.lote_id = l.id AND e.fecha_salida IS NULL
         ORDER BY e.fecha_entrada DESC LIMIT 1) AS biomasa_inicial_actual
FROM lotes_ganado l
"""


def _a_agregado(fila: asyncpg.Record) -> LoteGanado:
    return LoteGanado(
        id=LoteId(fila["id"]),
        finca_id=FincaId(fila["finca_id"]),
        nombre=fila["nombre"],
        n_animales=fila["n_animales"],
        peso_promedio_kg=float(fila["peso_promedio_kg"]),
        potrero_actual_id=fila["potrero_actual_id"],
        biomasa_inicial_actual=(
            float(fila["biomasa_inicial_actual"])
            if fila["biomasa_inicial_actual"] is not None
            else None
        ),
    )


class PostgresLoteRepository(LoteRepository):
    def __init__(self, pool: asyncpg.Pool, organizacion_id: uuid.UUID) -> None:
        self._pool = pool
        self._organizacion_id = organizacion_id

    async def guardar(self, lote: LoteGanado) -> None:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            await con.execute(
                """
                INSERT INTO lotes_ganado
                  (id, finca_id, nombre, n_animales, peso_promedio_kg, potrero_actual_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                  nombre = EXCLUDED.nombre,
                  n_animales = EXCLUDED.n_animales,
                  peso_promedio_kg = EXCLUDED.peso_promedio_kg,
                  potrero_actual_id = EXCLUDED.potrero_actual_id
                """,
                lote.id,
                lote.finca_id,
                lote.nombre,
                lote.n_animales,
                lote.peso_promedio_kg,
                lote.potrero_actual_id,
            )

    async def obtener(self, lote_id: LoteId) -> LoteGanado | None:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            fila = await con.fetchrow(_SELECT + "WHERE l.id = $1", lote_id)
        return _a_agregado(fila) if fila else None

    async def listar_por_finca(self, finca_id: FincaId) -> list[LoteGanado]:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            filas = await con.fetch(
                _SELECT + "WHERE l.finca_id = $1 ORDER BY l.nombre NULLS LAST", finca_id
            )
        return [_a_agregado(f) for f in filas]
