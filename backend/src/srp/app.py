"""Fábrica de la aplicación FastAPI (adaptador de entrada HTTP).

Los routers de cada contexto se registran aquí en la etapa de integración;
cada contexto exporta un `APIRouter` standalone desde su
`infrastructure/api/` y no conoce a la app.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from srp.shared.db import crear_pool
from srp.shared.events import BusEventosEnMemoria


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.pool = await crear_pool()
    app.state.bus = BusEventosEnMemoria()
    yield
    await app.state.pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="SRP — Sistema de Rotación de Pastos", lifespan=_lifespan)

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # Registro de routers de contextos (etapa de integración):
    # from srp.gestion_potreros.infrastructure.api.router import router as potreros_router
    # app.include_router(potreros_router)
    return app
