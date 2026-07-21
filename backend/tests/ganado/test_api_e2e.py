"""Tests e2e HTTP del router de ganado (ASGI in-process, Postgres real)."""

from __future__ import annotations

import uuid
from datetime import date

import httpx
import pytest
from fastapi import FastAPI

from srp.ganado.domain.events import LoteEntroAPotrero, LoteSalioDePotrero
from srp.ganado.infrastructure.api.router import router
from srp.shared.auth import emitir_token_dev
from srp.shared.events import BusEventosEnMemoria


@pytest.fixture
async def cliente(pool, organizacion):
    org_id, _finca_id = organizacion
    app = FastAPI()
    app.include_router(router)
    # Estado que en producción deja el lifespan de srp.app
    app.state.pool = pool
    app.state.bus = BusEventosEnMemoria()
    token = emitir_token_dev("test-user", org_id)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        client.app = app  # acceso al bus en los tests
        yield client


async def test_sin_token_devuelve_401(cliente):
    r = await cliente.get(
        "/fincas/00000000-0000-0000-0000-000000000000/lotes",
        headers={"Authorization": ""},
    )
    assert r.status_code == 401


async def test_ciclo_completo_http(cliente, organizacion, potrero, pool):
    _org_id, finca_id = organizacion
    recibidos = []
    bus = cliente.app.state.bus
    bus.suscribir(LoteEntroAPotrero, recibidos.append)
    bus.suscribir(LoteSalioDePotrero, recibidos.append)

    # POST /lotes/
    r = await cliente.post(
        "/lotes/",
        json={
            "finca_id": str(finca_id),
            "nombre": "Lote HTTP",
            "n_animales": 20,
            "peso_promedio_kg": 450,
        },
    )
    assert r.status_code == 201, r.text
    lote = r.json()
    assert lote["ua_equivalente"] == 20.0

    # GET /fincas/{finca_id}/lotes
    r = await cliente.get(f"/fincas/{finca_id}/lotes")
    assert r.status_code == 200
    assert [fila["id"] for fila in r.json()] == [lote["id"]]

    # POST /eventos/entrada
    r = await cliente.post(
        "/eventos/entrada",
        json={
            "lote_id": lote["id"],
            "potrero_id": str(potrero),
            "fecha": "2026-07-01",
            "biomasa_inicial": 2800,
        },
    )
    assert r.status_code == 200, r.text
    entrada = r.json()
    assert entrada["fecha_entrada"] == "2026-07-01"
    assert entrada["fecha_salida"] is None

    # entrada doble → 409
    r = await cliente.post(
        "/eventos/entrada",
        json={"lote_id": lote["id"], "potrero_id": str(potrero)},
    )
    assert r.status_code == 409

    # POST /eventos/salida (fecha por defecto: hoy)
    r = await cliente.post(
        "/eventos/salida",
        json={"lote_id": lote["id"], "biomasa_final": 1500},
    )
    assert r.status_code == 200, r.text
    salida = r.json()
    assert salida["id"] == entrada["id"]
    assert salida["fecha_salida"] == date.today().isoformat()
    assert salida["biomasa_final"] == 1500.0

    # salida sin estar en potrero → 409
    r = await cliente.post("/eventos/salida", json={"lote_id": lote["id"]})
    assert r.status_code == 409

    # lote inexistente → 404
    r = await cliente.post(
        "/eventos/salida",
        json={"lote_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 404

    # Eventos de dominio publicados por el bus
    assert [type(e).__name__ for e in recibidos] == [
        "LoteEntroAPotrero",
        "LoteSalioDePotrero",
    ]
    assert recibidos[1].biomasa_inicial == 2800.0
    assert recibidos[1].biomasa_final == 1500.0

    # Fila persistida con entrada y salida
    fila = await pool.fetchrow(
        "SELECT fecha_entrada, fecha_salida FROM eventos_pastoreo WHERE id = $1",
        uuid.UUID(entrada["id"]),
    )
    assert fila["fecha_entrada"] == date(2026, 7, 1)
    assert fila["fecha_salida"] == date.today()
