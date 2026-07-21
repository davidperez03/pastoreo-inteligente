"""Adaptador de salida: repositorio de potreros sobre Postgres+PostGIS (§18.4).

Toda operación pasa por `conexion_org` para que la RLS multi-tenant (§2, §19)
aplique con el `organizacion_id` del token.
"""

from __future__ import annotations

import json
import uuid

import asyncpg

from srp.gestion_potreros.domain.entities import Potrero
from srp.gestion_potreros.domain.ports.potrero_repository import PotreroRepository
from srp.gestion_potreros.domain.value_objects import EstadoPotrero, FactorFatiga, Geometria
from srp.shared.db import conexion_org
from srp.shared.types import Coordenada, FincaId, PotreroId

_COLUMNAS = """
    id, finca_id, nombre, ST_AsGeoJSON(geom)::text AS geojson, area_ha,
    especie_pasto_id, tipo_suelo, fuente_agua, factor_fatiga, estado,
    fecha_ultima_salida, biomasa_actual_kg_ms_ha, metodo_levantamiento, accuracy_m
"""


class PostgresPotreroRepository(PotreroRepository):
    def __init__(self, pool: asyncpg.Pool, organizacion_id: uuid.UUID) -> None:
        self._pool = pool
        self._organizacion_id = organizacion_id

    async def guardar(self, potrero: Potrero) -> None:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            await con.execute(
                """
                INSERT INTO potreros
                  (id, finca_id, nombre, geom, especie_pasto_id, tipo_suelo,
                   fuente_agua, factor_fatiga, estado, fecha_ultima_salida,
                   biomasa_actual_kg_ms_ha, metodo_levantamiento, accuracy_m)
                VALUES
                  ($1, $2, $3, ST_GeomFromGeoJSON($4)::geography, $5, $6,
                   $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (id) DO UPDATE SET
                  nombre = EXCLUDED.nombre,
                  geom = EXCLUDED.geom,
                  especie_pasto_id = EXCLUDED.especie_pasto_id,
                  tipo_suelo = EXCLUDED.tipo_suelo,
                  fuente_agua = EXCLUDED.fuente_agua,
                  factor_fatiga = EXCLUDED.factor_fatiga,
                  estado = EXCLUDED.estado,
                  fecha_ultima_salida = EXCLUDED.fecha_ultima_salida,
                  biomasa_actual_kg_ms_ha = EXCLUDED.biomasa_actual_kg_ms_ha,
                  metodo_levantamiento = EXCLUDED.metodo_levantamiento,
                  accuracy_m = EXCLUDED.accuracy_m,
                  actualizado_en = now()
                """,
                potrero.id,
                potrero.finca_id,
                potrero.nombre,
                json.dumps(potrero.geojson),
                potrero.especie_pasto_id,
                potrero.tipo_suelo,
                potrero.fuente_agua,
                potrero.factor_fatiga.valor,
                potrero.estado.value,
                potrero.fecha_ultima_salida,
                potrero.biomasa_actual_kg_ms_ha,
                potrero.geometria.metodo_levantamiento,
                potrero.geometria.accuracy_m,
            )

    async def obtener(self, id: PotreroId) -> Potrero | None:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            fila = await con.fetchrow(
                f"SELECT {_COLUMNAS} FROM potreros WHERE id = $1", id
            )
        return self._a_entidad(fila) if fila else None

    async def listar_por_finca(self, finca_id: FincaId) -> list[Potrero]:
        async with conexion_org(self._pool, self._organizacion_id) as con:
            filas = await con.fetch(
                f"SELECT {_COLUMNAS} FROM potreros WHERE finca_id = $1 ORDER BY nombre",
                finca_id,
            )
        return [self._a_entidad(f) for f in filas]

    @staticmethod
    def _a_entidad(fila: asyncpg.Record) -> Potrero:
        geojson = json.loads(fila["geojson"])
        anillo = geojson["coordinates"][0]
        puntos = [Coordenada(lat=float(lat), lng=float(lng)) for lng, lat, *_ in anillo]
        if len(puntos) > 1 and puntos[0] == puntos[-1]:
            puntos = puntos[:-1]  # la Geometria del dominio guarda el anillo sin cerrar
        geometria = Geometria(
            puntos=tuple(puntos),
            metodo_levantamiento=fila["metodo_levantamiento"],
            accuracy_m=float(fila["accuracy_m"]) if fila["accuracy_m"] is not None else None,
        )
        return Potrero.reconstituir(
            id=PotreroId(fila["id"]),
            finca_id=FincaId(fila["finca_id"]),
            nombre=fila["nombre"],
            geometria=geometria,
            geojson=geojson,
            area_ha=float(fila["area_ha"]),
            especie_pasto_id=fila["especie_pasto_id"],
            tipo_suelo=fila["tipo_suelo"],
            fuente_agua=fila["fuente_agua"],
            factor_fatiga=FactorFatiga(float(fila["factor_fatiga"])),
            estado=EstadoPotrero(fila["estado"]),
            fecha_ultima_salida=fila["fecha_ultima_salida"],
            biomasa_actual_kg_ms_ha=(
                float(fila["biomasa_actual_kg_ms_ha"])
                if fila["biomasa_actual_kg_ms_ha"] is not None
                else None
            ),
        )
