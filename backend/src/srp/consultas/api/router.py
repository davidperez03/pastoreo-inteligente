"""Router de consultas (lado de lectura). Espera `app.state.pool`."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from srp.consultas.historial_potrero import (
    DIAS_DEFAULT,
    PotreroNoVisible,
    historial_potrero,
)
from srp.shared.auth import UsuarioActual, get_current_user
from srp.shared.types import PotreroId

router = APIRouter(tags=["consultas"])


class PuntoHistorialResponse(BaseModel):
    """Contrato con el frontend (`PuntoHistorial` en components/dashboard/tipos.ts)."""

    fecha: str
    biomasa_modelo: float | None
    biomasa_ndvi: float | None
    evento: str | None


@router.get(
    "/potreros/{potrero_id}/historial",
    response_model=list[PuntoHistorialResponse],
)
async def historial(
    potrero_id: uuid.UUID,
    request: Request,
    dias: int = Query(DIAS_DEFAULT, ge=1, le=366),
    user: UsuarioActual = Depends(get_current_user),
) -> list[PuntoHistorialResponse]:
    try:
        puntos = await historial_potrero(
            request.app.state.pool,
            user.organizacion_id,
            PotreroId(potrero_id),
            dias=dias,
        )
    except PotreroNoVisible:
        raise HTTPException(404, "Potrero no encontrado") from None
    return [
        PuntoHistorialResponse(
            fecha=p.fecha.isoformat(),
            biomasa_modelo=p.biomasa_modelo,
            biomasa_ndvi=p.biomasa_ndvi,
            evento=p.evento,
        )
        for p in puntos
    ]
