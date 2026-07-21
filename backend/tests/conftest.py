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


ROL_SIN_BYPASS = "srp_test_app"


@pytest.fixture
async def pool_sin_bypass(pool):
    """Pool conectado con un rol SIN BYPASSRLS, para tests que deben probar
    aislamiento multi-tenant de verdad.

    El fixture `pool` normal conecta como `srp` (owner del docker-compose
    local), que es superusuario y bypasea la RLS igual que el rol admin de
    Supabase — cualquier test que use `pool` para verificar "esta
    organización no ve datos de otra" pasaría aunque la política RLS
    estuviera rota. Este rol es el equivalente local de `srp_app`
    (scripts/crear_rol_app.py en Supabase): mismos privilegios de datos,
    sin bypass.
    """
    await pool.execute(f"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROL_SIN_BYPASS}') THEN
            CREATE ROLE {ROL_SIN_BYPASS} WITH LOGIN PASSWORD 'test'
              NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
          END IF;
        END
        $$;
        GRANT USAGE ON SCHEMA public TO {ROL_SIN_BYPASS};
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROL_SIN_BYPASS};
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROL_SIN_BYPASS};
    """)
    dsn_base = _database_url().rsplit("@", 1)[-1]
    dsn = f"postgresql://{ROL_SIN_BYPASS}:test@{dsn_base}"
    pool_restringido = await asyncpg.create_pool(dsn)
    yield pool_restringido
    await pool_restringido.close()
