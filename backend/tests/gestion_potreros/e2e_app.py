"""App FastAPI mínima para la verificación e2e de esta unidad.

El router del contexto es standalone (no está registrado en srp.app todavía);
aquí se monta sobre una app con lifespan que crea el pool, igual que hará la
etapa de integración.

Uso: PYTHONPATH=src uvicorn tests.gestion_potreros.e2e_app:app --port 8012
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from srp.gestion_potreros.infrastructure.api.router import router
from srp.shared.db import crear_pool
from srp.shared.events import BusEventosEnMemoria


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.pool = await crear_pool()
    app.state.bus = BusEventosEnMemoria()
    yield
    await app.state.pool.close()


app = FastAPI(title="SRP e2e — Gestión de Potreros", lifespan=_lifespan)
app.include_router(router)
