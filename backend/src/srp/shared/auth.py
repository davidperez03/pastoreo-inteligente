"""Autenticación JWT y contexto de organización (§10).

El token (estilo Supabase Auth) lleva `sub` (usuario) y `organizacion_id` en
los claims. `organizacion_id` se propaga a `app.current_org` en la conexión de
base de datos para que la RLS del esquema (§2) aplique automáticamente.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request

ALGORITMO = "HS256"


def _secreto() -> str:
    return os.environ.get("SRP_JWT_SECRET", "dev-secret-inseguro")


@dataclass(frozen=True)
class UsuarioActual:
    user_id: str
    organizacion_id: uuid.UUID
    rol: str  # 'admin' | 'operador'


def emitir_token_dev(user_id: str, organizacion_id: uuid.UUID, rol: str = "admin") -> str:
    """Solo para desarrollo y tests. En producción los tokens los emite el
    proveedor de auth (Supabase Auth), no el backend."""
    return jwt.encode(
        {"sub": user_id, "organizacion_id": str(organizacion_id), "rol": rol},
        _secreto(),
        algorithm=ALGORITMO,
    )


def get_current_user(request: Request) -> UsuarioActual:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Falta token Bearer")
    try:
        claims = jwt.decode(auth.removeprefix("Bearer "), _secreto(), algorithms=[ALGORITMO])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Token inválido: {exc}") from exc
    try:
        return UsuarioActual(
            user_id=claims["sub"],
            organizacion_id=uuid.UUID(claims["organizacion_id"]),
            rol=claims.get("rol", "operador"),
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(401, "Token sin organizacion_id válido") from exc


def requiere_admin(user: UsuarioActual = Depends(get_current_user)) -> UsuarioActual:
    if user.rol != "admin":
        raise HTTPException(403, "Requiere rol admin")
    return user
