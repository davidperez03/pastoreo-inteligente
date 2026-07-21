"""Adaptador de entrada HTTP del contexto Gestión de Ganado (§18.1).

Router standalone: la app lo registra en la etapa de integración
(`app.include_router(router)`); este módulo no conoce a la app. Requiere
`app.state.pool` (asyncpg.Pool) y `app.state.bus` (PublicadorEventos),
tal como los deja el lifespan de `srp.app`.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from srp.ganado.application.dto import EventoPastoreoDTO, LoteDTO
from srp.ganado.application.errors import LoteNoEncontrado
from srp.ganado.application.use_cases import (
    CrearLote,
    ListarLotes,
    RegistrarEntrada,
    RegistrarSalida,
)
from srp.ganado.domain.errors import DomainError
from srp.ganado.infrastructure.adapters.postgres_eventos_pastoreo_repository import (
    PostgresEventosPastoreoRepository,
)
from srp.ganado.infrastructure.adapters.postgres_lote_repository import (
    PostgresLoteRepository,
)
from srp.shared.auth import UsuarioActual, get_current_user
from srp.shared.types import FincaId, LoteId, PotreroId

router = APIRouter(tags=["ganado"])


# ---- Modelos de request/response (adaptador HTTP; no son el dominio) ----


class CrearLoteRequest(BaseModel):
    finca_id: uuid.UUID
    nombre: str = Field(min_length=1)
    n_animales: int = Field(gt=0)
    peso_promedio_kg: float = Field(gt=0)


class LoteResponse(BaseModel):
    id: uuid.UUID
    finca_id: uuid.UUID
    nombre: str | None
    n_animales: int
    peso_promedio_kg: float
    ua_equivalente: float
    potrero_actual_id: uuid.UUID | None

    @classmethod
    def desde_dto(cls, dto: LoteDTO) -> LoteResponse:
        return cls(**dto.__dict__)


class RegistrarEntradaRequest(BaseModel):
    lote_id: uuid.UUID
    potrero_id: uuid.UUID
    fecha: date | None = None
    biomasa_inicial: float | None = Field(default=None, ge=0)


class RegistrarSalidaRequest(BaseModel):
    lote_id: uuid.UUID
    fecha: date | None = None
    biomasa_final: float | None = Field(default=None, ge=0)


class EventoPastoreoResponse(BaseModel):
    id: uuid.UUID
    lote_id: uuid.UUID
    potrero_id: uuid.UUID
    fecha_entrada: date
    fecha_salida: date | None
    biomasa_inicial: float | None
    biomasa_final: float | None

    @classmethod
    def desde_dto(cls, dto: EventoPastoreoDTO) -> EventoPastoreoResponse:
        return cls(**dto.__dict__)


# ---- Wiring por request ----


def _lotes_repo(request: Request, user: UsuarioActual) -> PostgresLoteRepository:
    return PostgresLoteRepository(request.app.state.pool, user.organizacion_id)


def _eventos_repo(
    request: Request, user: UsuarioActual
) -> PostgresEventosPastoreoRepository:
    return PostgresEventosPastoreoRepository(request.app.state.pool, user.organizacion_id)


# ---- Endpoints ----


@router.post("/lotes/", response_model=LoteResponse, status_code=201)
async def crear_lote(
    data: CrearLoteRequest,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> LoteResponse:
    caso = CrearLote(_lotes_repo(request, user))
    try:
        dto = await caso.ejecutar(
            finca_id=FincaId(data.finca_id),
            nombre=data.nombre,
            n_animales=data.n_animales,
            peso_promedio_kg=data.peso_promedio_kg,
        )
    except DomainError as exc:
        raise HTTPException(422, str(exc)) from exc
    return LoteResponse.desde_dto(dto)


@router.get("/fincas/{finca_id}/lotes", response_model=list[LoteResponse])
async def listar_lotes(
    finca_id: uuid.UUID,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> list[LoteResponse]:
    caso = ListarLotes(_lotes_repo(request, user))
    return [
        LoteResponse.desde_dto(dto) for dto in await caso.ejecutar(FincaId(finca_id))
    ]


@router.post("/eventos/entrada", response_model=EventoPastoreoResponse)
async def registrar_entrada(
    data: RegistrarEntradaRequest,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> EventoPastoreoResponse:
    caso = RegistrarEntrada(
        _lotes_repo(request, user),
        _eventos_repo(request, user),
        request.app.state.bus,
    )
    try:
        dto = await caso.ejecutar(
            lote_id=LoteId(data.lote_id),
            potrero_id=PotreroId(data.potrero_id),
            fecha=data.fecha,
            biomasa_inicial=data.biomasa_inicial,
        )
    except LoteNoEncontrado as exc:
        raise HTTPException(404, str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(409, str(exc)) from exc
    return EventoPastoreoResponse.desde_dto(dto)


@router.post("/eventos/salida", response_model=EventoPastoreoResponse)
async def registrar_salida(
    data: RegistrarSalidaRequest,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> EventoPastoreoResponse:
    caso = RegistrarSalida(
        _lotes_repo(request, user),
        _eventos_repo(request, user),
        request.app.state.bus,
    )
    try:
        dto = await caso.ejecutar(
            lote_id=LoteId(data.lote_id),
            fecha=data.fecha,
            biomasa_final=data.biomasa_final,
        )
    except LoteNoEncontrado as exc:
        raise HTTPException(404, str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(409, str(exc)) from exc
    return EventoPastoreoResponse.desde_dto(dto)
