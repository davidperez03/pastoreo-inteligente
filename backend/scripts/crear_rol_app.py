"""Crea (o rota la contraseña de) el rol de aplicación no-owner.

El rol `postgres` de Supabase (como el `srp` del docker-compose local) es
superusuario: bypasea la RLS por completo. La app y el worker deben conectar
con un rol normal, sin BYPASSRLS, para que las políticas de §2/§19 apliquen
de verdad. Ejecutar UNA VEZ contra el proyecto (o cuando se quiera rotar la
contraseña) con una conexión ADMIN (superuser):

    SUPABASE_DB_URL_ADMIN=... PYTHONPATH=src python scripts/crear_rol_app.py

Imprime el DSN completo del rol de app — pegarlo en .env como
SUPABASE_DB_URL_APP. Idempotente: si el rol ya existe, solo rota la
contraseña (nunca deja credenciales viejas activas).
"""

from __future__ import annotations

import asyncio
import os
import secrets
from urllib.parse import urlsplit, urlunsplit

import asyncpg

ROL_APP = "srp_app"


async def main() -> None:
    admin_dsn = os.environ["SUPABASE_DB_URL_ADMIN"]
    password = secrets.token_urlsafe(24)

    con = await asyncpg.connect(admin_dsn)
    try:
        existe = await con.fetchval(
            "SELECT 1 FROM pg_roles WHERE rolname = $1", ROL_APP
        )
        if existe:
            await con.execute(f"ALTER ROLE {ROL_APP} WITH PASSWORD '{password}'")
        else:
            # NOSUPERUSER NOBYPASSRLS explícitos: son el default para un rol
            # nuevo, pero lo dejamos escrito porque es la propiedad que
            # importa — un futuro ALTER accidental que agregue BYPASSRLS
            # sería el bug de seguridad más silencioso posible aquí.
            await con.execute(
                f"CREATE ROLE {ROL_APP} WITH LOGIN PASSWORD '{password}' "
                "NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE"
            )

        # Supabase instala PostGIS en el esquema "extensions", no en "public"
        # (a diferencia del docker-compose local, donde CREATE EXTENSION sin
        # SCHEMA lo deja en public). Sin esto en el search_path del rol, tipos
        # como GEOGRAPHY no resuelven: "type geography does not exist".
        await con.execute(
            f'ALTER ROLE {ROL_APP} SET search_path = "$user", public, extensions'
        )
        await con.execute(f"GRANT USAGE ON SCHEMA public TO {ROL_APP}")
        await con.execute(f"GRANT USAGE ON SCHEMA extensions TO {ROL_APP}")
        await con.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROL_APP}"
        )
        await con.execute(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROL_APP}"
        )
        # Privilegios por defecto para tablas que creen futuras migraciones
        # (ejecutadas por el rol admin) sin tener que repetir este script.
        await con.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {ROL_APP}"
        )
        await con.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {ROL_APP}"
        )
    finally:
        await con.close()

    # Reconstruye el DSN del rol de app sobre el mismo host/puerto/db que el
    # admin (pooler de sesión, IPv4). El pooler de Supabase (Supavisor)
    # enruta por el nombre de usuario: debe llevar el sufijo ".<project-ref>"
    # igual que el admin ("postgres.<ref>") — un usuario "pelado" no rutea
    # al proyecto correcto.
    partes = urlsplit(admin_dsn)
    usuario_admin = partes.username or ""
    proyecto_ref = usuario_admin.split(".", 1)[-1]
    netloc = f"{ROL_APP}.{proyecto_ref}:{password}@{partes.hostname}:{partes.port}"
    dsn_app = urlunsplit(("postgresql", netloc, partes.path, "", ""))

    print(f"Rol {ROL_APP} listo. DSN de aplicación:\n")
    print(dsn_app)


if __name__ == "__main__":
    asyncio.run(main())
