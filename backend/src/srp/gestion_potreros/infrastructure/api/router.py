"""Adaptador de entrada HTTP (router FastAPI) del contexto Gestión de Potreros.

Router standalone (§18.1): se registra en la app en la etapa de integración.
Espera encontrar en `app.state` un `pool` asyncpg (y opcionalmente un `bus`
PublicadorEventos; si no hay, crea un bus en memoria propio). La organización
sale del token JWT (`get_current_user`) y se propaga a la RLS vía
`conexion_org` dentro del repositorio.
"""

from __future__ import annotations

import uuid
from datetime import date

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from srp.gestion_potreros.application.dto import (
    ImportarPlanimetriaCommand,
    PotreroDTO,
    RegistrarPotreroManualCommand,
)
from srp.gestion_potreros.application.use_cases.importar_planimetria import (
    ImportarPlanimetria,
)
from srp.gestion_potreros.application.use_cases.listar_potreros import (
    ListarPotreros,
    ObtenerPotrero,
)
from srp.gestion_potreros.application.use_cases.registrar_potrero_manual import (
    RegistrarPotreroManual,
)
from srp.gestion_potreros.domain.excepciones import DomainError
from srp.gestion_potreros.infrastructure.adapters.postgres_potrero_repository import (
    PostgresPotreroRepository,
)
from srp.gestion_potreros.infrastructure.adapters.shapely_geometria_validator import (
    GeometriaInvalida,
)
from srp.planimetria.validator import PlanimetriaGeometriaValidator
from srp.shared.auth import UsuarioActual, get_current_user
from srp.shared.events import BusEventosEnMemoria
from srp.shared.types import FincaId, PotreroId

router = APIRouter(prefix="", tags=["potreros"])


# ---- Modelos HTTP (pydantic — solo viven en este adaptador) ----


class PotreroCreate(BaseModel):
    finca_id: uuid.UUID
    nombre: str = Field(min_length=1)
    # Una de las dos entradas: puntos (lat, lng) o un GeoJSON Polygon/Feature
    puntos: list[tuple[float, float]] | None = None
    geojson: dict | None = None
    especie_pasto_id: uuid.UUID
    metodo_levantamiento: str = Field(min_length=1)
    tipo_suelo: str | None = None
    fuente_agua: bool = False
    accuracy_m: float | None = None


class PotreroResponse(BaseModel):
    id: uuid.UUID
    finca_id: uuid.UUID
    nombre: str
    area_ha: float
    estado: str
    especie_pasto_id: uuid.UUID
    tipo_suelo: str | None
    fuente_agua: bool
    factor_fatiga: float
    metodo_levantamiento: str
    accuracy_m: float | None
    fecha_ultima_salida: date | None
    biomasa_actual_kg_ms_ha: float | None
    geojson: dict
    advertencia: str | None = None

    @classmethod
    def desde_dto(cls, dto: PotreroDTO) -> PotreroResponse:
        return cls(
            id=dto.id,
            finca_id=dto.finca_id,
            nombre=dto.nombre,
            area_ha=dto.area_ha,
            estado=dto.estado,
            especie_pasto_id=dto.especie_pasto_id,
            tipo_suelo=dto.tipo_suelo,
            fuente_agua=dto.fuente_agua,
            factor_fatiga=dto.factor_fatiga,
            metodo_levantamiento=dto.metodo_levantamiento,
            accuracy_m=dto.accuracy_m,
            fecha_ultima_salida=dto.fecha_ultima_salida,
            biomasa_actual_kg_ms_ha=dto.biomasa_actual_kg_ms_ha,
            geojson=dto.geojson,
            advertencia=dto.advertencia,
        )


# ---- Wiring por request (composición de adaptadores) ----


def _pool(request: Request) -> asyncpg.Pool:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(503, "Pool de base de datos no inicializado")
    return pool


def _bus(request: Request):
    bus = getattr(request.app.state, "bus", None)
    if bus is None:
        bus = BusEventosEnMemoria()
        request.app.state.bus = bus
    return bus


def _repo(request: Request, user: UsuarioActual) -> PostgresPotreroRepository:
    return PostgresPotreroRepository(_pool(request), user.organizacion_id)


# ---- Endpoints ----


@router.post("/potreros/", status_code=201, response_model=PotreroResponse)
async def crear_potrero(
    body: PotreroCreate,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> PotreroResponse:
    if (body.puntos is None) == (body.geojson is None):
        raise HTTPException(422, "Debe enviarse exactamente uno de: puntos | geojson")

    repo = _repo(request, user)
    # Adaptador completo del paquete planimetría (§3): mismo puerto del kernel
    # que el ShapelyGeometriaValidator mínimo, con parsers y validaciones extra.
    validador = PlanimetriaGeometriaValidator()
    bus = _bus(request)
    try:
        if body.puntos is not None:
            dto = await RegistrarPotreroManual(repo, validador, bus).ejecutar(
                RegistrarPotreroManualCommand(
                    finca_id=FincaId(body.finca_id),
                    nombre=body.nombre,
                    puntos=tuple((lat, lng) for lat, lng in body.puntos),
                    especie_pasto_id=body.especie_pasto_id,
                    metodo_levantamiento=body.metodo_levantamiento,
                    tipo_suelo=body.tipo_suelo,
                    fuente_agua=body.fuente_agua,
                    accuracy_m=body.accuracy_m,
                )
            )
        else:
            assert body.geojson is not None
            dto = await ImportarPlanimetria(repo, validador, bus).ejecutar(
                ImportarPlanimetriaCommand(
                    finca_id=FincaId(body.finca_id),
                    nombre=body.nombre,
                    geojson=body.geojson,
                    especie_pasto_id=body.especie_pasto_id,
                    metodo_levantamiento=body.metodo_levantamiento,
                    tipo_suelo=body.tipo_suelo,
                    fuente_agua=body.fuente_agua,
                    accuracy_m=body.accuracy_m,
                )
            )
    except (GeometriaInvalida, ValueError, DomainError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            409, f"Ya existe un potrero llamado {body.nombre!r} en esa finca"
        ) from exc
    except asyncpg.ForeignKeyViolationError as exc:
        raise HTTPException(422, "finca_id o especie_pasto_id inexistente") from exc
    return PotreroResponse.desde_dto(dto)


@router.get("/fincas/{finca_id}/potreros", response_model=list[PotreroResponse])
async def listar_potreros_de_finca(
    finca_id: uuid.UUID,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> list[PotreroResponse]:
    dtos = await ListarPotreros(_repo(request, user)).ejecutar(FincaId(finca_id))
    return [PotreroResponse.desde_dto(d) for d in dtos]


@router.get("/potreros/{potrero_id}", response_model=PotreroResponse)
async def obtener_potrero(
    potrero_id: uuid.UUID,
    request: Request,
    user: UsuarioActual = Depends(get_current_user),
) -> PotreroResponse:
    dto = await ObtenerPotrero(_repo(request, user)).ejecutar(PotreroId(potrero_id))
    if dto is None:
        raise HTTPException(404, "Potrero no encontrado")
    return PotreroResponse.desde_dto(dto)
