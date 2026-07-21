"""Test e2e HTTP del endpoint de sugerencia (router + auth JWT + Postgres),
sirviendo la app in-process con httpx.ASGITransport."""

from __future__ import annotations

import uuid

import httpx
from fastapi import FastAPI

from srp.rotacion.infrastructure.api.router import router
from srp.shared.auth import emitir_token_dev
from tests.rotacion.test_proyeccion import _insertar_potrero


def _app_con_pool(pool) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.pool = pool  # el lifespan real lo crea srp.app; aquí lo inyectamos
    return app


async def test_sugerir_rotacion_http(pool, organizacion):
    org_id, finca_id = organizacion
    p_chico, _ = await _insertar_potrero(pool, finca_id, "Chico", 1800.0)
    p_grande, _ = await _insertar_potrero(pool, finca_id, "Grande", 4200.0)
    lote_id = uuid.uuid4()
    await pool.execute(
        """
        INSERT INTO lotes_ganado (id, finca_id, nombre, n_animales, peso_promedio_kg)
        VALUES ($1, $2, 'Lote e2e', 20, 450)
        """,
        lote_id,
        finca_id,
    )
    try:
        transport = httpx.ASGITransport(app=_app_con_pool(pool))
        token = emitir_token_dev("test-user", org_id)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Sin token: 401.
            r = await client.get(f"/fincas/{finca_id}/rotacion/sugerir")
            assert r.status_code == 401

            r = await client.get(
                f"/fincas/{finca_id}/rotacion/sugerir",
                params={"horizonte_dias": 30},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        cuerpo = r.json()
        assert cuerpo["finca_id"] == str(finca_id)
        assert cuerpo["horizonte_dias"] == 30
        assert cuerpo["movimientos"], "debe haber al menos un movimiento"
        primero = cuerpo["movimientos"][0]
        assert primero["lote_id"] == str(lote_id)
        assert primero["potrero_id"] == str(p_grande), (
            "el primer destino debe ser el potrero de mayor biomasa"
        )
        # Fechas en ISO (YYYY-MM-DD).
        assert len(primero["fecha"]) == 10 and primero["fecha"][4] == "-"
        assert isinstance(cuerpo["advertencias"], list)
    finally:
        await pool.execute("DELETE FROM lotes_ganado WHERE id = $1", lote_id)
        await pool.execute(
            "DELETE FROM potreros WHERE id = ANY($1::uuid[])", [p_chico, p_grande]
        )
