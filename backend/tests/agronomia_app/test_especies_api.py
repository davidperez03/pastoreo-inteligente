"""E2E HTTP de /especies-pasto contra Postgres real (seeds de migración 0001)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from srp.agronomia.infrastructure.api.router import router
from srp.shared.auth import emitir_token_dev


@pytest.fixture
async def cliente(pool):
    app = FastAPI()
    app.state.pool = pool
    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_lista_especies_seed(cliente):
    token = emitir_token_dev("u1", uuid.uuid4(), "admin")
    resp = await cliente.get(
        "/especies-pasto", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    nombres = {e["nombre"] for e in resp.json()}
    assert "Brachiaria decumbens" in nombres
    assert len(resp.json()) >= 5


async def test_sin_token_401(cliente):
    resp = await cliente.get("/especies-pasto")
    assert resp.status_code == 401
