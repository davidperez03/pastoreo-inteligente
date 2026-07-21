"""Crea (o reutiliza) un usuario de Supabase Auth y lo vincula a una
organización en nuestra tabla `usuarios`. Imprime un access_token real
(emitido por Supabase, firmado con el JWT secret del proyecto) listo para
probar la API contra el modo Supabase de `get_current_user`.

Uso:
    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
    SUPABASE_ANON_KEY=... SUPABASE_DB_URL_ADMIN=... \
    PYTHONPATH=src python scripts/crear_usuario_supabase.py \
        --email demo@srp.test --password "Demo1234!" \
        --organizacion 11111111-1111-1111-1111-111111111111 --rol admin

Requiere que la organización ya exista (ver backend/scripts/seed_demo.py).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import uuid

import asyncpg
import httpx


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--organizacion", required=True, type=uuid.UUID)
    parser.add_argument("--rol", default="admin", choices=["admin", "operador"])
    args = parser.parse_args()

    supabase_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]

    async with httpx.AsyncClient() as http:
        # Admin API: crea el usuario con el email ya confirmado (evita el
        # paso de verificación por correo, innecesario para un usuario de
        # prueba/piloto creado por un admin).
        resp = await http.post(
            f"{supabase_url}/auth/v1/admin/users",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            json={
                "email": args.email,
                "password": args.password,
                "email_confirm": True,
            },
        )
        if resp.status_code == 422 and "already been registered" in resp.text:
            # Idempotencia: si ya existe, lo buscamos por email para obtener su id.
            resp = await http.get(
                f"{supabase_url}/auth/v1/admin/users",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                },
                params={"email": args.email},
            )
            resp.raise_for_status()
            usuarios = resp.json().get("users", [])
            if not usuarios:
                raise RuntimeError(f"Usuario {args.email} no encontrado tras 422")
            user_id = uuid.UUID(usuarios[0]["id"])
        else:
            resp.raise_for_status()
            user_id = uuid.UUID(resp.json()["id"])

        # Access token real: inicia sesión como el propio usuario (password
        # grant), igual que haría el frontend con supabase-js.
        login = await http.post(
            f"{supabase_url}/auth/v1/token?grant_type=password",
            headers={"apikey": anon_key},
            json={"email": args.email, "password": args.password},
        )
        login.raise_for_status()
        access_token = login.json()["access_token"]

    con = await asyncpg.connect(os.environ["SUPABASE_DB_URL_ADMIN"])
    try:
        await con.execute(
            """
            INSERT INTO usuarios (id, organizacion_id, rol, email)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE
              SET organizacion_id = EXCLUDED.organizacion_id,
                  rol = EXCLUDED.rol,
                  email = EXCLUDED.email
            """,
            user_id,
            args.organizacion,
            args.rol,
            args.email,
        )
    finally:
        await con.close()

    print(f"Usuario {args.email} ({user_id}) vinculado a {args.organizacion} como {args.rol}\n")
    print("access_token (real, emitido por Supabase Auth):\n")
    print(access_token)


if __name__ == "__main__":
    asyncio.run(main())
