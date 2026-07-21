"""Tests del handler de estado ante eventos de pastoreo, contra Postgres real.

No prueban la RLS en sí (el rol local `srp` es owner y la bypasea — solo el
smoke contra Supabase con el rol no-owner `srp_app` prueba eso de verdad);
prueban que el handler resuelve la organización correcta del potrero antes de
escribir y que el estado queda persistido, protegiendo contra una regresión
que vuelva a escribir sin `conexion_org` (el bug real que motivó este test:
funcionaba en local por el bypass de owner y hubiera fallado en silencio en
producción).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

import pytest

from srp.gestion_potreros.infrastructure.adapters.estado_potrero_handler import (
    EstadoPotreroHandler,
    PotreroSinOrganizacion,
)

GEOM = (
    "POLYGON((-72.396 5.337, -72.392 5.337, -72.392 5.341, "
    "-72.396 5.341, -72.396 5.337))"
)


@dataclass(frozen=True)
class _EventoFake:
    potrero_id: uuid.UUID
    fecha: date


@pytest.fixture
async def potrero(pool, organizacion):
    _, finca_id = organizacion
    potrero_id = uuid.uuid4()
    await pool.execute(
        f"""
        INSERT INTO potreros (id, finca_id, nombre, geom, especie_pasto_id,
                              metodo_levantamiento, estado)
        SELECT $1, $2, 'Handler-P1', ST_GeogFromText('{GEOM}'), id, 'test', 'descanso'
        FROM especies_pasto LIMIT 1
        """,
        potrero_id,
        finca_id,
    )
    yield potrero_id
    await pool.execute("DELETE FROM potreros WHERE id = $1", potrero_id)


async def test_al_entrar_lote_marca_ocupado(pool, potrero):
    handler = EstadoPotreroHandler(pool)
    await handler.al_entrar_lote(_EventoFake(potrero_id=potrero, fecha=date.today()))
    estado = await pool.fetchval("SELECT estado FROM potreros WHERE id = $1", potrero)
    assert estado == "ocupado"


async def test_al_salir_lote_marca_descanso_y_fecha(pool, potrero):
    handler = EstadoPotreroHandler(pool)
    hoy = date.today()
    await handler.al_entrar_lote(_EventoFake(potrero_id=potrero, fecha=hoy))
    await handler.al_salir_lote(_EventoFake(potrero_id=potrero, fecha=hoy))
    fila = await pool.fetchrow(
        "SELECT estado, fecha_ultima_salida FROM potreros WHERE id = $1", potrero
    )
    assert fila["estado"] == "descanso"
    assert fila["fecha_ultima_salida"] == hoy


async def test_potrero_inexistente_no_falla_el_handler(pool):
    handler = EstadoPotreroHandler(pool)
    # No debe lanzar: el bus ya loguea y sigue ante un potrero que no resuelve
    # organización (borrado entre el evento y el handler).
    await handler.al_entrar_lote(
        _EventoFake(potrero_id=uuid.uuid4(), fecha=date.today())
    )


async def test_organizacion_del_potrero_resuelve_via_finca(pool, potrero, organizacion):
    org_id, _ = organizacion
    handler = EstadoPotreroHandler(pool)
    resuelto = await handler._organizacion_del_potrero(potrero)
    assert resuelto == org_id


async def test_organizacion_del_potrero_inexistente_lanza(pool):
    handler = EstadoPotreroHandler(pool)
    with pytest.raises(PotreroSinOrganizacion):
        await handler._organizacion_del_potrero(uuid.uuid4())
