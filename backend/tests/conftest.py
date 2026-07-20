"""Fixtures compartidas. Los tests que necesitan base de datos asumen un
Postgres+PostGIS accesible en DATABASE_URL (levantado con `make db-up` /
docker compose) y las migraciones aplicadas (`make migrate`).

Los tests puros de dominio no deben usar estas fixtures.
"""

from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

from srp.shared.events import BusEventosEnMemoria


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://srp:srp@localhost:5432/srp")


@pytest.fixture
async def pool():
    try:
        pool = await asyncpg.create_pool(_database_url())
    except OSError:
        pytest.skip("Base de datos no disponible (make db-up && make migrate)")
    yield pool
    await pool.close()


@pytest.fixture
async def organizacion(pool):
    """Crea una organización + finca de prueba y devuelve (org_id, finca_id)."""
    org_id = uuid.uuid4()
    finca_id = uuid.uuid4()
    await pool.execute(
        "INSERT INTO organizaciones (id, nombre) VALUES ($1, 'Org Test')", org_id
    )
    await pool.execute(
        "INSERT INTO fincas (id, organizacion_id, nombre) VALUES ($1, $2, 'Finca Test')",
        finca_id,
        org_id,
    )
    yield org_id, finca_id
    await pool.execute("DELETE FROM fincas WHERE id = $1", finca_id)
    await pool.execute("DELETE FROM organizaciones WHERE id = $1", org_id)


@pytest.fixture
def bus() -> BusEventosEnMemoria:
    return BusEventosEnMemoria()
