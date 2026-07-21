"""Acceso a base de datos: pool asyncpg y contexto de organización para RLS."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager

import asyncpg


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://srp:srp@localhost:5432/srp")


async def crear_pool(dsn: str | None = None) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn or database_url(),
        # "extensions" además del "$user", public por defecto: Supabase
        # instala PostGIS ahí (no en public), y sin esto tipos como GEOGRAPHY
        # no resuelven para un rol no-owner. Se pasa como parámetro de
        # arranque de conexión (no ALTER ROLE) porque el pooler de sesión de
        # Supabase no aplicaba de forma confiable el search_path configurado
        # a nivel de rol al proxear la conexión. Un esquema "extensions"
        # inexistente (Postgres local) se ignora sin error.
        server_settings={"search_path": '"$user",public,extensions'},
    )


@asynccontextmanager
async def conexion_org(pool: asyncpg.Pool, organizacion_id: uuid.UUID):
    """Adquiere una conexión con `app.current_org` fijado para la RLS (§2, §10).

    Todo acceso a tablas con RLS debe pasar por aquí; una conexión sin el
    setting ve cero filas (la política usa current_setting(..., true) y un
    valor ausente no matchea ninguna organización).
    """
    async with pool.acquire() as con:
        await con.execute(
            "SELECT set_config('app.current_org', $1, false)", str(organizacion_id)
        )
        try:
            yield con
        finally:
            await con.execute("SELECT set_config('app.current_org', '', false)")
