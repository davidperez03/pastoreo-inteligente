"""Tests de persistencia idempotente contra Postgres real (§11)."""

from __future__ import annotations

from datetime import date

from srp.agronomia.infra_clima.repositorio_clima import (
    guardar_registros,
    ultimo_registro,
)
from srp.shared.types import RegistroClima


async def test_guardar_dos_veces_mismo_dia_no_duplica_y_actualiza(pool, estacion):
    fecha = date(2026, 7, 19)
    version_1 = RegistroClima(
        fecha=fecha,
        temp_media=25.0,
        temp_max=30.0,
        temp_min=21.0,
        precipitacion_mm=2.5,
    )
    # Reejecución del job con datos corregidos por el proveedor
    version_2 = RegistroClima(
        fecha=fecha,
        temp_media=25.9,
        temp_max=30.6,
        temp_min=22.4,
        precipitacion_mm=0.0,
        humedad_suelo_pct=41.0,
        estimado=False,
    )

    await guardar_registros(pool, estacion, [version_1])
    await guardar_registros(pool, estacion, [version_2])

    filas = await pool.fetch(
        "SELECT * FROM registros_clima WHERE estacion_clima_id = $1 AND fecha = $2",
        estacion,
        fecha,
    )
    assert len(filas) == 1
    fila = filas[0]
    assert float(fila["temp_media"]) == 25.9
    assert float(fila["temp_max"]) == 30.6
    assert float(fila["temp_min"]) == 22.4
    assert float(fila["precipitacion_mm"]) == 0.0
    assert float(fila["humedad_suelo_pct"]) == 41.0
    assert fila["estimado"] is False


async def test_ultimo_registro_devuelve_el_mas_reciente(pool, estacion):
    registros = [
        RegistroClima(
            fecha=date(2026, 7, 17),
            temp_media=26.2,
            temp_max=31.4,
            temp_min=22.1,
            precipitacion_mm=4.2,
        ),
        RegistroClima(
            fecha=date(2026, 7, 19),
            temp_media=25.9,
            temp_max=30.6,
            temp_min=22.4,
            precipitacion_mm=0.0,
        ),
        RegistroClima(
            fecha=date(2026, 7, 18),
            temp_media=25.1,
            temp_max=29.8,
            temp_min=21.7,
            precipitacion_mm=18.7,
        ),
    ]
    await guardar_registros(pool, estacion, registros)

    ultimo = await ultimo_registro(pool, estacion)

    assert ultimo is not None
    assert ultimo.fecha == date(2026, 7, 19)
    assert ultimo.temp_media == 25.9
    assert ultimo.humedad_suelo_pct is None
    assert ultimo.estimado is False


async def test_ultimo_registro_sin_datos_devuelve_none(pool, estacion):
    assert await ultimo_registro(pool, estacion) is None


async def test_guardar_lista_vacia_no_falla(pool, estacion):
    await guardar_registros(pool, estacion, [])
    assert await ultimo_registro(pool, estacion) is None
