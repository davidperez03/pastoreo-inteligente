"""Fábrica de la aplicación FastAPI (composition root).

Aquí — y solo aquí — se conocen todos los contextos a la vez: se registran los
routers de entrada y se suscriben los handlers de integración al bus de
eventos. Los contextos entre sí solo se comunican por esos eventos (§17).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from srp.calibracion.application.handler import CalibrarPotreroAlSalirLote
from srp.calibracion.infrastructure.repositorio_sistema import (
    RepositorioCalibracionSistema,
)
from srp.consultas.api.router import router as consultas_router
from srp.ganado.domain.events import LoteEntroAPotrero, LoteSalioDePotrero
from srp.ganado.infrastructure.api.router import router as ganado_router
from srp.gestion_potreros.infrastructure.adapters.estado_potrero_handler import (
    EstadoPotreroHandler,
)
from srp.gestion_potreros.infrastructure.api.router import router as potreros_router
from srp.rotacion.infrastructure.api.router import router as rotacion_router
from srp.shared.db import crear_pool
from srp.shared.events import BusEventosEnMemoria


def _cablear_bus(bus: BusEventosEnMemoria, pool) -> None:
    """Suscripciones de integración entre contextos.

    El bus despacha por clase exacta: la clase canónica de los eventos de
    pastoreo es la del contexto Ganado (quien los publica); los consumidores
    definieron réplicas estructuralmente idénticas, por eso los handlers
    funcionan por duck typing sobre los mismos campos.
    """
    estado = EstadoPotreroHandler(pool)
    bus.suscribir(LoteEntroAPotrero, estado.al_entrar_lote)
    bus.suscribir(LoteSalioDePotrero, estado.al_salir_lote)

    calibrar = CalibrarPotreroAlSalirLote(RepositorioCalibracionSistema(pool))
    bus.suscribir(LoteSalioDePotrero, calibrar)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.pool = await crear_pool()
    app.state.bus = BusEventosEnMemoria()
    _cablear_bus(app.state.bus, app.state.pool)
    yield
    await app.state.pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="SRP — Sistema de Rotación de Pastos", lifespan=_lifespan)

    # Dev/demo: el frontend (puerto distinto) necesita CORS explícito para que
    # el navegador no bloquee las llamadas. SRP_CORS_ORIGINS (coma-separado)
    # sobreescribe el default en despliegues reales.
    origenes = os.environ.get(
        "SRP_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    app.include_router(potreros_router)
    app.include_router(ganado_router)
    app.include_router(rotacion_router)
    app.include_router(consultas_router)
    return app
