"""Proyección de lectura sobre Postgres (adaptador del puerto
`ProyeccionRotacion`).

CQRS ligero (§19.1): estas consultas son de SOLO lectura y cruzan contextos a
nivel de datos (tablas `potreros` y `lotes_ganado`, propiedad del contexto
Gestión de Potreros) — permitido para proyecciones de consulta; jamás se
escribe desde aquí. Toda conexión pasa por `conexion_org` para que la RLS
multi-tenant (§2) filtre por organización.
"""

from __future__ import annotations

import uuid

import asyncpg

from srp.rotacion.application.sugerir_rotacion import ProyeccionRotacion
from srp.shared.db import conexion_org
from srp.shared.types import FincaId, LoteSnapshot, PotreroSnapshot

# Fallback conservador cuando la especie no define días de descanso ideal.
_DIAS_DESCANSO_POR_DEFECTO = 30

_SQL_POTREROS = """
SELECT p.id, p.finca_id, p.nombre, p.area_ha, p.estado,
       p.biomasa_actual_kg_ms_ha, p.factor_fatiga,
       COALESCE(e.dias_descanso_ideal, $2) AS dias_descanso_ideal,
       p.fecha_ultima_salida, p.fuente_agua
FROM potreros p
JOIN especies_pasto e ON e.id = p.especie_pasto_id
WHERE p.finca_id = $1
ORDER BY p.nombre
"""

_SQL_LOTES = """
SELECT id, finca_id, n_animales, ua_equivalente, potrero_actual_id
FROM lotes_ganado
WHERE finca_id = $1
ORDER BY id
"""


class ProyeccionRotacionPostgres(ProyeccionRotacion):
    def __init__(self, pool: asyncpg.Pool, organizacion_id: uuid.UUID) -> None:
        self._pool = pool
        self._organizacion_id = organizacion_id

    async def potreros_de_finca(self, finca_id: FincaId) -> list[PotreroSnapshot]:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            filas = await con.fetch(_SQL_POTREROS, finca_id, _DIAS_DESCANSO_POR_DEFECTO)
        return [
            PotreroSnapshot(
                id=f["id"],
                finca_id=f["finca_id"],
                nombre=f["nombre"],
                area_ha=float(f["area_ha"] or 0),
                estado=f["estado"],
                biomasa_kg_ms_ha=(
                    float(f["biomasa_actual_kg_ms_ha"])
                    if f["biomasa_actual_kg_ms_ha"] is not None
                    else None
                ),
                factor_fatiga=float(f["factor_fatiga"]),
                dias_descanso_ideal=int(f["dias_descanso_ideal"]),
                fecha_ultima_salida=f["fecha_ultima_salida"],
                fuente_agua=f["fuente_agua"],
            )
            for f in filas
        ]

    async def lotes_de_finca(self, finca_id: FincaId) -> list[LoteSnapshot]:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            filas = await con.fetch(_SQL_LOTES, finca_id)
        return [
            LoteSnapshot(
                id=f["id"],
                finca_id=f["finca_id"],
                n_animales=f["n_animales"],
                ua_equivalente=float(f["ua_equivalente"]),
                potrero_actual_id=f["potrero_actual_id"],
            )
            for f in filas
        ]
