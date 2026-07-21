"""Autenticación JWT y contexto de organización (§10).

Dos modos, elegidos por la presencia de `SUPABASE_URL` en el entorno:

- **Modo Supabase** (`SUPABASE_URL` presente — despliegue real): el token lo
  emite Supabase Auth, firmado con la clave asimétrica del proyecto (ES256;
  los proyectos nuevos de Supabase ya no usan el secreto HS256 legado).
  Se verifica contra el endpoint JWKS público del proyecto
  (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`), sin necesidad de ningún
  secreto compartido. El token solo trae `sub` (el user id); la organización
  y el rol se resuelven consultando la tabla `usuarios` (puente entre
  `auth.users` y nuestro modelo de tenancy, §17.1 aplicado a identidad: este
  contexto es dueño exclusivo de esa tabla).
- **Modo desarrollo** (sin esa variable — local/tests, como hasta ahora): el
  token lo emite `emitir_token_dev`, con `organizacion_id`/`rol` embebidos
  directamente en el claim HS256, sin tocar la base de datos ni la red.

Los dos modos NUNCA están activos a la vez: si `SUPABASE_URL` está presente,
un token de desarrollo deja de aceptarse. Aceptar ambas firmas a la vez sería
la puerta trasera más silenciosa posible en un despliegue real donde alguien
olvidó limpiar `SRP_JWT_SECRET`.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient

ALGORITMO_DEV = "HS256"
# Algoritmos asimétricos que emite el sistema de llaves de Supabase Auth
# (ES256 es el default en proyectos nuevos; RS256 aparece en proyectos que
# migraron desde el esquema anterior). Lista cerrada a propósito: nunca se
# acepta HS256 aquí, para no exponer una vía de "alg confusion" que reutilice
# la clave pública como si fuera un secreto simétrico.
ALGORITMOS_SUPABASE = ["ES256", "RS256"]


def _secreto_dev() -> str:
    return os.environ.get("SRP_JWT_SECRET", "dev-secret-inseguro")


def _supabase_url() -> str | None:
    url = os.environ.get("SUPABASE_URL")
    return url.rstrip("/") if url else None


@lru_cache(maxsize=1)
def _jwks_client(supabase_url: str) -> PyJWKClient:
    # PyJWKClient cachea las llaves obtenidas (cache_keys=True por defecto)
    # y las refresca automáticamente si aparece un `kid` desconocido (p. ej.
    # tras rotar las llaves del proyecto) — no hace una llamada de red por
    # cada request.
    return PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")


@dataclass(frozen=True)
class UsuarioActual:
    user_id: str
    organizacion_id: uuid.UUID
    rol: str  # 'admin' | 'operador'


def emitir_token_dev(user_id: str, organizacion_id: uuid.UUID, rol: str = "admin") -> str:
    """Solo para desarrollo y tests, y solo válido cuando SUPABASE_URL NO
    está configurado (ver docstring del módulo)."""
    return jwt.encode(
        {"sub": user_id, "organizacion_id": str(organizacion_id), "rol": rol},
        _secreto_dev(),
        algorithm=ALGORITMO_DEV,
    )


async def get_current_user(request: Request) -> UsuarioActual:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Falta token Bearer")
    token = auth.removeprefix("Bearer ")

    supabase_url = _supabase_url()
    if supabase_url:
        return await _resolver_supabase(request, token, supabase_url)
    return _resolver_dev(token)


def _resolver_dev(token: str) -> UsuarioActual:
    try:
        claims = jwt.decode(token, _secreto_dev(), algorithms=[ALGORITMO_DEV])
        return UsuarioActual(
            user_id=claims["sub"],
            organizacion_id=uuid.UUID(claims["organizacion_id"]),
            rol=claims.get("rol", "operador"),
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Token inválido: {exc}") from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(401, "Token sin organizacion_id válido") from exc


async def _resolver_supabase(
    request: Request, token: str, supabase_url: str
) -> UsuarioActual:
    try:
        signing_key = _jwks_client(supabase_url).get_signing_key_from_jwt(token)
        # PyJWT exige verificar `aud` en cuanto el claim está presente en el
        # token, así que hay que pasarlo explícito (no basta con omitirlo).
        # "authenticated" es el valor fijo que emite Supabase Auth para
        # cualquier usuario con sesión iniciada.
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITMOS_SUPABASE,
            audience="authenticated",
        )
        user_id = claims["sub"]
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Token inválido: {exc}") from exc
    except KeyError as exc:
        raise HTTPException(401, "Token sin 'sub'") from exc

    pool = request.app.state.pool
    fila = await pool.fetchrow(
        "SELECT organizacion_id, rol FROM usuarios WHERE id = $1", uuid.UUID(user_id)
    )
    if fila is None:
        raise HTTPException(
            403,
            "Usuario autenticado pero no vinculado a ninguna organización "
            "(falta la fila en 'usuarios'; pídele a un admin que te agregue)",
        )
    return UsuarioActual(
        user_id=user_id, organizacion_id=fila["organizacion_id"], rol=fila["rol"]
    )


def requiere_admin(user: UsuarioActual = Depends(get_current_user)) -> UsuarioActual:
    if user.rol != "admin":
        raise HTTPException(403, "Requiere rol admin")
    return user
