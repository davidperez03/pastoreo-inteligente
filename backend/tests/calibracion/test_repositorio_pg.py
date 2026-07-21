"""E2E de la Unidad 8 contra Postgres real: bus -> handler -> repo Pg (§17).

Inserta un potrero por SQL con biomasa_actual y verifica que publicar el evento
`LoteSalioDePotrero` actualice `factor_fatiga`/`n_ciclos_observados` en la tabla.
Se salta automáticamente si no hay base de datos (fixture `pool`).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from srp.calibracion.application.handler import (
    CalibrarPotreroAlSalirLote,
    registrar_en_bus,
)
from srp.calibracion.domain.events import LoteSalioDePotrero
from srp.calibracion.infrastructure.repositorio_calibracion import (
    RepositorioCalibracionPg,
    leer_estado,
)
from srp.shared.db import conexion_org
from srp.shared.types import PotreroId

# Polígono de prueba (Casanare, Colombia) para la geometría obligatoria.
_GEOM_TEST = (
    "POLYGON((-72.396 5.337, -72.392 5.337, -72.392 5.341, "
    "-72.396 5.341, -72.396 5.337))"
)


@pytest.fixture
async def potrero(pool, organizacion):
    """Inserta un potrero de prueba con biomasa predicha y lo limpia al final."""
    org_id, finca_id = organizacion
    potrero_id = uuid.uuid4()
    async with conexion_org(pool, org_id) as con:
        especie_id = await con.fetchval(
            "SELECT id FROM especies_pasto WHERE nombre = 'Brachiaria decumbens'"
        )
        await con.execute(
            """
            INSERT INTO potreros
              (id, finca_id, nombre, geom, especie_pasto_id,
               factor_fatiga, n_ciclos_observados, biomasa_actual_kg_ms_ha,
               metodo_levantamiento)
            VALUES
              ($1, $2, 'Potrero U8', ST_GeogFromText($3), $4,
               1.0, 0, 100.0, 'test')
            """,
            potrero_id,
            finca_id,
            _GEOM_TEST,
            especie_id,
        )
    yield org_id, PotreroId(potrero_id)
    await pool.execute("DELETE FROM potreros WHERE id = $1", potrero_id)


async def test_publicar_evento_actualiza_potrero_en_postgres(pool, potrero, bus):
    org_id, potrero_id = potrero
    repo = RepositorioCalibracionPg(pool, org_id)
    registrar_en_bus(bus, CalibrarPotreroAlSalirLote(repo))

    await bus.publicar(
        [
            LoteSalioDePotrero(
                potrero_id=potrero_id,
                lote_id=None,
                fecha=date(2026, 7, 20),
                biomasa_inicial=2500.0,
                biomasa_final=80.0,  # error_relativo = 80/100 = 0.8
            )
        ]
    )

    factor, n_ciclos, biomasa_predicha = await leer_estado(pool, org_id, potrero_id)
    assert factor == pytest.approx(0.8)
    assert n_ciclos == 1
    # La predicción vigente no la escribe este contexto: sigue intacta.
    assert biomasa_predicha == pytest.approx(100.0)


async def test_evento_sin_biomasa_final_no_toca_postgres(pool, potrero, bus):
    org_id, potrero_id = potrero
    repo = RepositorioCalibracionPg(pool, org_id)
    registrar_en_bus(bus, CalibrarPotreroAlSalirLote(repo))

    await bus.publicar(
        [
            LoteSalioDePotrero(
                potrero_id=potrero_id,
                lote_id=None,
                fecha=date(2026, 7, 20),
                biomasa_inicial=2500.0,
                biomasa_final=None,
            )
        ]
    )

    factor, n_ciclos, _ = await leer_estado(pool, org_id, potrero_id)
    assert factor == pytest.approx(1.0)
    assert n_ciclos == 0
