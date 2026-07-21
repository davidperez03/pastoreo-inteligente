"""Catálogo de especies de pasto (solo lectura).

`especies_pasto` es dato de referencia compartido (sin RLS, igual para todas
las organizaciones); solo se exige autenticación, no aislamiento por
organización.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from srp.shared.auth import get_current_user

router = APIRouter(tags=["agronomia"])


class EspeciePastoResponse(BaseModel):
    id: uuid.UUID
    nombre: str
    dias_descanso_ideal: int | None


@router.get("/especies-pasto", response_model=list[EspeciePastoResponse])
async def listar_especies(
    request: Request, _user=Depends(get_current_user)
) -> list[EspeciePastoResponse]:
    pool = request.app.state.pool
    filas = await pool.fetch(
        "SELECT id, nombre, dias_descanso_ideal FROM especies_pasto ORDER BY nombre"
    )
    return [
        EspeciePastoResponse(
            id=f["id"], nombre=f["nombre"], dias_descanso_ideal=f["dias_descanso_ideal"]
        )
        for f in filas
    ]
