"""E2E HTTP de /fincas contra Postgres real, montando solo ese router."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from srp.organizaciones.infrastructure.api.router import router
from srp.shared.auth import emitir_token_dev


@pytest.fixture
async def cliente(pool):
    """Cliente con el pool owner — suficiente para probar forma de respuesta
    y errores; NO prueba aislamiento de RLS (ver `cliente_sin_bypass`)."""
    app = FastAPI()
    app.state.pool = pool
    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def cliente_sin_bypass(pool_sin_bypass):
    """Cliente con el pool sin BYPASSRLS — el único que prueba de verdad
    el aislamiento multi-tenant (igual que la app en producción)."""
    app = FastAPI()
    app.state.pool = pool_sin_bypass
    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_crear_y_listar_fincas(cliente_sin_bypass, organizacion, pool):
    org_id, finca_seed = organizacion
    token = emitir_token_dev("u1", org_id, "admin")
    headers = {"Authorization": f"Bearer {token}"}

    resp = await cliente_sin_bypass.post(
        "/fincas/", json={"nombre": "Finca Nueva"}, headers=headers
    )
    assert resp.status_code == 201
    creada = resp.json()
    assert creada["nombre"] == "Finca Nueva"

    try:
        resp = await cliente_sin_bypass.get("/fincas/", headers=headers)
        assert resp.status_code == 200
        nombres = {f["nombre"] for f in resp.json()}
        assert "Finca Nueva" in nombres
        assert "Finca Test" in nombres  # la del fixture organizacion
    finally:
        await pool.execute("DELETE FROM fincas WHERE id = $1", uuid.UUID(creada["id"]))


async def test_no_ve_fincas_de_otra_organizacion(cliente_sin_bypass, organizacion, pool):
    org_id, _ = organizacion
    otra_org = uuid.uuid4()
    await pool.execute(
        "INSERT INTO organizaciones (id, nombre) VALUES ($1, 'Otra')", otra_org
    )
    otra_finca = uuid.uuid4()
    await pool.execute(
        "INSERT INTO fincas (id, organizacion_id, nombre) VALUES ($1, $2, 'Ajena')",
        otra_finca,
        otra_org,
    )
    try:
        token = emitir_token_dev("u1", org_id, "admin")
        resp = await cliente_sin_bypass.get(
            "/fincas/", headers={"Authorization": f"Bearer {token}"}
        )
        nombres = {f["nombre"] for f in resp.json()}
        assert "Ajena" not in nombres
        assert nombres == {"Finca Test"}
    finally:
        await pool.execute("DELETE FROM fincas WHERE id = $1", otra_finca)
        await pool.execute("DELETE FROM organizaciones WHERE id = $1", otra_org)


async def test_finca_inexistente_404(cliente, organizacion):
    org_id, _ = organizacion
    token = emitir_token_dev("u1", org_id, "admin")
    resp = await cliente.get(
        f"/fincas/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


async def test_sin_token_401(cliente):
    resp = await cliente.get("/fincas/")
    assert resp.status_code == 401
