"""Tests de RepositorioCalibracionSistema contra Postgres real.

Mismo alcance/limitación que test_estado_potrero_handler.py: no prueban RLS
en sí (rol local `srp` es owner), prueban la resolución de organización y la
persistencia — protegen contra la regresión de volver a escribir sin
`conexion_org`.
"""

from __future__ import annotations

import uuid

import pytest

from srp.calibracion.infrastructure.repositorio_sistema import (
    PotreroSinOrganizacion,
    RepositorioCalibracionSistema,
)

GEOM = (
    "POLYGON((-72.396 5.337, -72.392 5.337, -72.392 5.341, "
    "-72.396 5.341, -72.396 5.337))"
)


@pytest.fixture
async def potrero(pool, organizacion):
    _, finca_id = organizacion
    potrero_id = uuid.uuid4()
    await pool.execute(
        f"""
        INSERT INTO potreros (id, finca_id, nombre, geom, especie_pasto_id,
                              metodo_levantamiento, factor_fatiga,
                              n_ciclos_observados, biomasa_actual_kg_ms_ha)
        SELECT $1, $2, 'Sistema-P1', ST_GeogFromText('{GEOM}'), id, 'test',
               1.0, 0, 1800
        FROM especies_pasto LIMIT 1
        """,
        potrero_id,
        finca_id,
    )
    yield potrero_id
    await pool.execute("DELETE FROM potreros WHERE id = $1", potrero_id)


async def test_leer_estado_resuelve_organizacion_y_lee(pool, potrero):
    repo = RepositorioCalibracionSistema(pool)
    factor, n_ciclos, biomasa = await repo.leer_estado(potrero)
    assert factor == 1.0
    assert n_ciclos == 0
    assert biomasa == 1800.0


async def test_guardar_estado_persiste(pool, potrero):
    repo = RepositorioCalibracionSistema(pool)
    await repo.guardar_estado(potrero, 0.82, 3)
    factor, n_ciclos, _ = await repo.leer_estado(potrero)
    assert factor == pytest.approx(0.82)
    assert n_ciclos == 3


async def test_potrero_inexistente_leer_devuelve_none(pool):
    repo = RepositorioCalibracionSistema(pool)
    assert await repo.leer_estado(uuid.uuid4()) is None


async def test_potrero_inexistente_guardar_lanza(pool):
    repo = RepositorioCalibracionSistema(pool)
    with pytest.raises(PotreroSinOrganizacion):
        await repo.guardar_estado(uuid.uuid4(), 0.9, 1)
