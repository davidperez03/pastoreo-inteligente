"""Tests de los adaptadores Postgres contra la base real (§14).

Requieren Postgres+PostGIS con migraciones aplicadas (fixture `pool` hace
skip si no hay base disponible).
"""

from __future__ import annotations

import uuid
from datetime import date

from srp.ganado.domain.entities import LoteGanado
from srp.ganado.infrastructure.adapters.postgres_eventos_pastoreo_repository import (
    PostgresEventosPastoreoRepository,
)
from srp.ganado.infrastructure.adapters.postgres_lote_repository import (
    PostgresLoteRepository,
)
from srp.shared.types import FincaId, LoteId, PotreroId


def _nuevo_lote(finca_id, **kwargs) -> LoteGanado:
    defaults = dict(
        id=LoteId(uuid.uuid4()),
        finca_id=FincaId(finca_id),
        nombre="Lote Repo",
        n_animales=20,
        peso_promedio_kg=450.0,
    )
    defaults.update(kwargs)
    return LoteGanado(**defaults)


async def test_guardar_y_obtener_lote(pool, organizacion, potrero):
    org_id, finca_id = organizacion
    repo = PostgresLoteRepository(pool, org_id)
    lote = _nuevo_lote(finca_id)

    await repo.guardar(lote)
    leido = await repo.obtener(lote.id)

    assert leido is not None
    assert leido.id == lote.id
    assert leido.finca_id == finca_id
    assert leido.nombre == "Lote Repo"
    assert leido.n_animales == 20
    assert leido.peso_promedio_kg == 450.0
    assert leido.ua_equivalente == 20.0  # columna generada coincide con el dominio
    assert leido.potrero_actual_id is None


async def test_obtener_lote_inexistente_devuelve_none(pool, organizacion, potrero):
    org_id, _finca_id = organizacion
    repo = PostgresLoteRepository(pool, org_id)
    assert await repo.obtener(LoteId(uuid.uuid4())) is None


async def test_guardar_es_upsert(pool, organizacion, potrero):
    org_id, finca_id = organizacion
    repo = PostgresLoteRepository(pool, org_id)
    lote = _nuevo_lote(finca_id)
    await repo.guardar(lote)

    actualizado = _nuevo_lote(
        finca_id, id=lote.id, nombre="Renombrado", n_animales=25,
        potrero_actual_id=PotreroId(potrero),
    )
    await repo.guardar(actualizado)

    leido = await repo.obtener(lote.id)
    assert leido.nombre == "Renombrado"
    assert leido.n_animales == 25
    assert leido.potrero_actual_id == potrero


async def test_listar_por_finca(pool, organizacion, potrero):
    org_id, finca_id = organizacion
    repo = PostgresLoteRepository(pool, org_id)
    await repo.guardar(_nuevo_lote(finca_id, nombre="A"))
    await repo.guardar(_nuevo_lote(finca_id, nombre="B"))

    lotes = await repo.listar_por_finca(FincaId(finca_id))
    assert [lote.nombre for lote in lotes] == ["A", "B"]


async def test_ciclo_evento_pastoreo(pool, organizacion, potrero):
    org_id, finca_id = organizacion
    lotes = PostgresLoteRepository(pool, org_id)
    eventos = PostgresEventosPastoreoRepository(pool, org_id)
    lote = _nuevo_lote(finca_id)
    await lotes.guardar(lote)

    # abrir
    abierto = await eventos.abrir_evento(
        lote.id, PotreroId(potrero), date(2026, 7, 1), biomasa_inicial=2800.0
    )
    assert abierto.abierto
    assert abierto.biomasa_inicial == 2800.0

    encontrado = await eventos.evento_abierto_de_lote(lote.id)
    assert encontrado is not None
    assert encontrado.id == abierto.id

    # el repo de lotes expone la biomasa inicial del ciclo abierto
    await lotes.guardar(
        _nuevo_lote(finca_id, id=lote.id, potrero_actual_id=PotreroId(potrero))
    )
    releido = await lotes.obtener(lote.id)
    assert releido.biomasa_inicial_actual == 2800.0

    # cerrar
    cerrado = await eventos.cerrar_evento(
        abierto.id, fecha_salida=date(2026, 7, 5), biomasa_final=1500.0
    )
    assert cerrado.fecha_salida == date(2026, 7, 5)
    assert cerrado.biomasa_final == 1500.0
    assert not cerrado.abierto

    assert await eventos.evento_abierto_de_lote(lote.id) is None

    # verificación directa en la tabla
    fila = await pool.fetchrow(
        "SELECT fecha_entrada, fecha_salida, biomasa_inicial, biomasa_final "
        "FROM eventos_pastoreo WHERE id = $1",
        abierto.id,
    )
    assert fila["fecha_entrada"] == date(2026, 7, 1)
    assert fila["fecha_salida"] == date(2026, 7, 5)
    assert float(fila["biomasa_inicial"]) == 2800.0
    assert float(fila["biomasa_final"]) == 1500.0
