"""Tests del job semanal de NDVI: persistencia idempotente y scheduler sin
arrancar (§6, §11).
"""

from __future__ import annotations

from datetime import date

import pytest

from srp.agronomia.infra_ndvi.adapter import NdviNoDisponibleError
from srp.agronomia.infra_ndvi.job import crear_scheduler_ndvi, sincronizar_ndvi_semanal
from srp.shared.ports import ProveedorNdvi
from srp.shared.types import LecturaNdvi


class AdapterFake(ProveedorNdvi):
    def __init__(self, lectura: LecturaNdvi | None = None):
        self.lectura = lectura
        self.poligonos: list[dict] = []

    async def obtener_ndvi(self, poligono_geojson: dict, fecha: date) -> LecturaNdvi:
        self.poligonos.append(poligono_geojson)
        if self.lectura is None:
            raise NdviNoDisponibleError("sin escena ni historial (simulado)")
        return self.lectura


async def test_job_persiste_lectura_por_potrero(pool, potrero):
    fecha = date(2026, 7, 19)
    adapter = AdapterFake(
        LecturaNdvi(fecha=fecha, ndvi_promedio=0.47, calidad=0.85)
    )

    resultado = await sincronizar_ndvi_semanal(pool, adapter, fecha=fecha)

    assert resultado["ok"] >= 1
    # El adapter recibió un GeoJSON Polygon válido del potrero
    assert any(p.get("type") == "Polygon" for p in adapter.poligonos)
    fila = await pool.fetchrow(
        "SELECT ndvi_promedio, stale FROM lecturas_ndvi WHERE potrero_id = $1 AND fecha = $2",
        potrero,
        fecha,
    )
    assert fila is not None
    assert float(fila["ndvi_promedio"]) == pytest.approx(0.47)
    assert fila["stale"] is False

    # Reejecutar el job no duplica filas (§11)
    await sincronizar_ndvi_semanal(pool, adapter, fecha=fecha)
    n = await pool.fetchval(
        "SELECT count(*) FROM lecturas_ndvi WHERE potrero_id = $1 AND fecha = $2",
        potrero,
        fecha,
    )
    assert n == 1


async def test_job_no_aborta_ante_potrero_sin_dato(pool, potrero):
    adapter = AdapterFake(lectura=None)  # siempre falla

    resultado = await sincronizar_ndvi_semanal(pool, adapter, fecha=date(2026, 7, 19))

    assert resultado["fallidos"] >= 1  # registró el fallo y siguió


async def test_scheduler_semanal_configurado_sin_arrancar(pool):
    scheduler = crear_scheduler_ndvi(pool, AdapterFake())

    assert scheduler.running is False  # el proceso dueño decide cuándo arrancar
    trabajo = scheduler.get_job("sincronizar_ndvi_semanal")
    assert trabajo is not None
    trigger = str(trabajo.trigger)
    assert "day_of_week='sun'" in trigger
    assert "hour='3'" in trigger
    assert str(scheduler.timezone) == "America/Bogota"
