"""App FastAPI mínima para la verificación e2e de la unidad 7: solo el
router de rotación + pool asyncpg. Uso:

    PYTHONPATH=src uvicorn tests.rotacion.e2e_app:app --port 8017
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from srp.rotacion.infrastructure.api.router import router
from srp.shared.db import crear_pool


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.pool = await crear_pool()
    yield
    await app.state.pool.close()


app = FastAPI(title="SRP e2e — rotación", lifespan=_lifespan)
app.include_router(router)
