"""App FastAPI standalone para verificación e2e de la Unidad 6.

Solo monta el router del contexto Gestión de Ganado; NO es la app de
producción (`srp.app` registra los routers en la etapa de integración).

Uso: PYTHONPATH=src uvicorn tests.ganado.e2e_app:app --port 8016
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from srp.ganado.infrastructure.api.router import router
from srp.shared.db import crear_pool
from srp.shared.events import BusEventosEnMemoria


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.pool = await crear_pool()
    app.state.bus = BusEventosEnMemoria()
    yield
    await app.state.pool.close()


app = FastAPI(title="SRP e2e — Gestión de Ganado", lifespan=_lifespan)
app.include_router(router)
