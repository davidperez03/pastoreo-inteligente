"""Tests de persistencia NDVI contra Postgres real: idempotencia (§11) y
recuperación de la última lectura.
"""

from __future__ import annotations

from datetime import date

import pytest

from srp.agronomia.infra_ndvi.repositorio_ndvi import guardar_lectura, ultima_lectura
from srp.shared.types import LecturaNdvi


async def test_guardar_lectura_es_idempotente(pool, potrero):
    fecha = date(2026, 7, 12)
    await guardar_lectura(
        pool, potrero, LecturaNdvi(fecha=fecha, ndvi_promedio=0.44, calidad=0.7)
    )
    # Reejecución del job con dato corregido: misma clave (potrero, fecha)
    await guardar_lectura(
        pool,
        potrero,
        LecturaNdvi(fecha=fecha, ndvi_promedio=0.51, calidad=0.95, stale=False),
    )

    filas = await pool.fetch(
        "SELECT * FROM lecturas_ndvi WHERE potrero_id = $1 AND fecha = $2",
        potrero,
        fecha,
    )
    assert len(filas) == 1  # ON CONFLICT: sin duplicados
    fila = filas[0]
    assert float(fila["ndvi_promedio"]) == pytest.approx(0.51)
    assert float(fila["cobertura_nubes_pct"]) == pytest.approx(5.0)  # (1-0.95)*100
    assert fila["stale"] is False
    assert fila["fuente"] == "sentinel-2"


async def test_ultima_lectura_devuelve_la_mas_reciente(pool, potrero):
    await guardar_lectura(
        pool, potrero, LecturaNdvi(fecha=date(2026, 7, 5), ndvi_promedio=0.40)
    )
    await guardar_lectura(
        pool,
        potrero,
        LecturaNdvi(
            fecha=date(2026, 7, 12), ndvi_promedio=0.55, calidad=0.8, stale=True
        ),
    )

    lectura = await ultima_lectura(pool, potrero)

    assert lectura is not None
    assert lectura.fecha == date(2026, 7, 12)
    assert lectura.ndvi_promedio == pytest.approx(0.55)
    assert lectura.calidad == pytest.approx(0.8)  # round-trip vía cobertura_nubes_pct
    assert lectura.stale is True
    assert lectura.fuente == "sentinel-2"


async def test_ultima_lectura_sin_historial_es_none(pool, potrero):
    assert await ultima_lectura(pool, potrero) is None
