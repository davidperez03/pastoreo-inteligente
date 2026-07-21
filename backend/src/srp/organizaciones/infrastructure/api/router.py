"""CRUD mínimo de fincas dentro de la organización del usuario autenticado.

Router standalone (§18.1), registrado en la etapa de integración. Espera
`app.state.pool` en `request.app.state`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from srp.shared.auth import UsuarioActual, get_current_user
from srp.shared.db import conexion_org

router = APIRouter(tags=["fincas"])


class FincaCreate(BaseModel):
    nombre: str = Field(min_length=1)


class FincaResponse(BaseModel):
    id: uuid.UUID
    nombre: str
    estacion_clima_id: uuid.UUID | None


@router.post("/fincas/", response_model=FincaResponse, status_code=201)
async def crear_finca(
    body: FincaCreate,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> FincaResponse:
    pool = request.app.state.pool
    finca_id = uuid.uuid4()
    async with conexion_org(pool, user.organizacion_id) as con:
        await con.execute(
            "INSERT INTO fincas (id, organizacion_id, nombre) VALUES ($1, $2, $3)",
            finca_id,
            user.organizacion_id,
            body.nombre,
        )
    return FincaResponse(id=finca_id, nombre=body.nombre, estacion_clima_id=None)


@router.get("/fincas/", response_model=list[FincaResponse])
async def listar_fincas(
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> list[FincaResponse]:
    pool = request.app.state.pool
    async with conexion_org(pool, user.organizacion_id) as con:
        filas = await con.fetch(
            "SELECT id, nombre, estacion_clima_id FROM fincas ORDER BY nombre"
        )
    return [
        FincaResponse(
            id=f["id"], nombre=f["nombre"], estacion_clima_id=f["estacion_clima_id"]
        )
        for f in filas
    ]


@router.get("/fincas/{finca_id}", response_model=FincaResponse)
async def obtener_finca(
    finca_id: uuid.UUID,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> FincaResponse:
    pool = request.app.state.pool
    async with conexion_org(pool, user.organizacion_id) as con:
        fila = await con.fetchrow(
            "SELECT id, nombre, estacion_clima_id FROM fincas WHERE id = $1", finca_id
        )
    if fila is None:
        raise HTTPException(404, "Finca no encontrada")
    return FincaResponse(
        id=fila["id"], nombre=fila["nombre"], estacion_clima_id=fila["estacion_clima_id"]
    )
