"""Tests de integración del repositorio contra Postgres+PostGIS real.

Usa las fixtures `pool` / `organizacion` de tests/conftest.py. Como los tests
conectan con el rol owner (`srp`), la RLS se bypassa — verificar la política
RLS con un rol no-owner es parte de la etapa de integración, no de esta unidad.
"""

from __future__ import annotations

import uuid

import pytest

from srp.gestion_potreros.domain.entities import Potrero
from srp.gestion_potreros.domain.value_objects import EstadoPotrero, FactorFatiga, Geometria
from srp.gestion_potreros.infrastructure.adapters.postgres_potrero_repository import (
    PostgresPotreroRepository,
)
from srp.gestion_potreros.infrastructure.adapters.shapely_geometria_validator import (
    ShapelyGeometriaValidator,
)
from srp.shared.types import Coordenada, FincaId, PotreroId
from tests.gestion_potreros.test_casos_uso import PUNTOS


@pytest.fixture
async def especie_id(pool) -> uuid.UUID:
    fila = await pool.fetchrow("SELECT id FROM especies_pasto LIMIT 1")
    assert fila, "Faltan seeds de especies_pasto (alembic upgrade head)"
    return fila["id"]


@pytest.fixture
async def repo(pool, organizacion):
    org_id, _ = organizacion
    yield PostgresPotreroRepository(pool, org_id)
    # limpieza: la fixture `organizacion` borra finca/org; potreros primero
    await pool.execute(
        "DELETE FROM potreros WHERE finca_id = $1", organizacion[1]
    )


def _potrero(finca_id: uuid.UUID, especie_id: uuid.UUID, nombre: str = "P-1") -> Potrero:
    resultado = ShapelyGeometriaValidator().construir_y_validar(list(PUNTOS))
    geometria = Geometria(
        puntos=tuple(Coordenada(lat, lng) for lat, lng in PUNTOS),
        metodo_levantamiento="gps_app",
        accuracy_m=4.5,
    )
    return Potrero.crear(
        finca_id=FincaId(finca_id),
        nombre=nombre,
        geometria=geometria,
        geojson=resultado["geojson"],
        area_ha=resultado["area_ha"],
        especie_pasto_id=especie_id,
        tipo_suelo="franco",
        fuente_agua=True,
    )


async def test_guardar_y_obtener_reconstituye_el_agregado(repo, organizacion, especie_id):
    _, finca_id = organizacion
    potrero = _potrero(finca_id, especie_id)
    await repo.guardar(potrero)

    leido = await repo.obtener(potrero.id)
    assert leido is not None
    assert leido.id == potrero.id
    assert leido.nombre == "P-1"
    assert leido.finca_id == finca_id
    assert leido.especie_pasto_id == especie_id
    assert leido.tipo_suelo == "franco"
    assert leido.fuente_agua is True
    assert leido.estado is EstadoPotrero.DESCANSO
    assert leido.factor_fatiga == FactorFatiga.neutro()
    assert leido.geometria.metodo_levantamiento == "gps_app"
    assert leido.geometria.accuracy_m == 4.5
    assert len(leido.geometria.puntos) == 4
    # area_ha la calcula el trigger de la BD (esferoide) — debe coincidir con
    # la aproximación EPSG:9377 del validador dentro de un margen razonable
    assert leido.area_ha == pytest.approx(19.6, rel=0.02)
    assert leido.eventos_pendientes() == []  # reconstitución no emite eventos


async def test_obtener_inexistente_devuelve_none(repo):
    assert await repo.obtener(PotreroId(uuid.uuid4())) is None


async def test_listar_por_finca(repo, organizacion, especie_id):
    _, finca_id = organizacion
    await repo.guardar(_potrero(finca_id, especie_id, nombre="B-2"))
    await repo.guardar(_potrero(finca_id, especie_id, nombre="A-1"))

    potreros = await repo.listar_por_finca(FincaId(finca_id))
    assert [p.nombre for p in potreros] == ["A-1", "B-2"]  # ordenado por nombre


async def test_guardar_persiste_transicion_de_estado(repo, organizacion, especie_id):
    _, finca_id = organizacion
    potrero = _potrero(finca_id, especie_id, nombre="C-3")
    await repo.guardar(potrero)

    potrero.registrar_entrada_lote()
    potrero.registrar_salida_lote(biomasa_final=1500.0)
    await repo.guardar(potrero)  # upsert

    leido = await repo.obtener(potrero.id)
    assert leido is not None
    assert leido.estado is EstadoPotrero.DESCANSO
    assert leido.fecha_ultima_salida == potrero.fecha_ultima_salida
    assert leido.biomasa_actual_kg_ms_ha == 1500.0


async def test_nombre_duplicado_en_finca_viola_unique(repo, organizacion, especie_id):
    import asyncpg

    _, finca_id = organizacion
    await repo.guardar(_potrero(finca_id, especie_id, nombre="Repetido"))
    with pytest.raises(asyncpg.UniqueViolationError):
        await repo.guardar(_potrero(finca_id, especie_id, nombre="Repetido"))
