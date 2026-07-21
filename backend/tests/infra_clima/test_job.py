"""Tests del job diario de clima con proveedor fake contra Postgres real."""

from __future__ import annotations

from datetime import date

import pytest

from srp.agronomia.infra_clima.job import crear_scheduler, sincronizar_clima_diario
from srp.shared.ports import ProveedorClima
from srp.shared.types import Coordenada, RegistroClima


class ProveedorFake(ProveedorClima):
    """Devuelve un clima determinista y registra las llamadas recibidas."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[Coordenada, date]] = []

    async def obtener_clima_diario(
        self, ubicacion: Coordenada, fecha: date
    ) -> RegistroClima:
        self.llamadas.append((ubicacion, fecha))
        return RegistroClima(
            fecha=fecha,
            temp_media=25.9,
            temp_max=30.6,
            temp_min=22.4,
            precipitacion_mm=3.1,
        )


class ProveedorCaido(ProveedorClima):
    async def obtener_clima_diario(
        self, ubicacion: Coordenada, fecha: date
    ) -> RegistroClima:
        raise ConnectionError("caído")


@pytest.fixture
async def finca_con_estacion(pool, organizacion, estacion):
    """Asigna la estación de prueba a la finca de prueba."""
    _, finca_id = organizacion
    await pool.execute(
        "UPDATE fincas SET estacion_clima_id = $1 WHERE id = $2", estacion, finca_id
    )
    yield finca_id, estacion
    await pool.execute(
        "UPDATE fincas SET estacion_clima_id = NULL WHERE id = $1", finca_id
    )


async def test_job_persiste_clima_de_ayer_por_estacion(pool, finca_con_estacion):
    _, estacion_id = finca_con_estacion
    proveedor = ProveedorFake()
    fecha = date(2026, 7, 19)

    sincronizadas = await sincronizar_clima_diario(pool, proveedor, fecha=fecha)

    assert sincronizadas == 1
    assert len(proveedor.llamadas) == 1
    ubicacion, fecha_pedida = proveedor.llamadas[0]
    assert fecha_pedida == fecha
    # Coordenadas de la estación (Yopal) leídas vía ST_Y/ST_X
    assert ubicacion.lat == pytest.approx(5.3378, abs=1e-4)
    assert ubicacion.lng == pytest.approx(-72.3959, abs=1e-4)

    fila = await pool.fetchrow(
        "SELECT * FROM registros_clima WHERE estacion_clima_id = $1 AND fecha = $2",
        estacion_id,
        fecha,
    )
    assert fila is not None
    assert float(fila["temp_media"]) == 25.9
    assert float(fila["precipitacion_mm"]) == 3.1
    assert fila["estimado"] is False


async def test_job_es_idempotente_al_reejecutar(pool, finca_con_estacion):
    _, estacion_id = finca_con_estacion
    fecha = date(2026, 7, 19)

    await sincronizar_clima_diario(pool, ProveedorFake(), fecha=fecha)
    await sincronizar_clima_diario(pool, ProveedorFake(), fecha=fecha)

    n_filas = await pool.fetchval(
        "SELECT count(*) FROM registros_clima WHERE estacion_clima_id = $1 AND fecha = $2",
        estacion_id,
        fecha,
    )
    assert n_filas == 1


async def test_job_ignora_fincas_sin_estacion(pool, organizacion):
    """La finca del fixture no tiene estación asignada: el job no hace nada."""
    proveedor = ProveedorFake()

    await sincronizar_clima_diario(pool, proveedor, fecha=date(2026, 7, 19))

    finca_id = organizacion[1]
    assert await pool.fetchval(
        "SELECT count(*) FROM registros_clima rc "
        "JOIN fincas f ON f.estacion_clima_id = rc.estacion_clima_id "
        "WHERE f.id = $1",
        finca_id,
    ) == 0


async def test_job_con_proveedor_caido_y_sin_historico_no_revienta(
    pool, finca_con_estacion
):
    """Un fallo total en una estación no debe tumbar el job completo (§11)."""
    sincronizadas = await sincronizar_clima_diario(
        pool, ProveedorCaido(), fecha=date(2026, 7, 19)
    )
    assert sincronizadas == 0


async def test_job_con_proveedor_caido_usa_fallback_estimado(
    pool, finca_con_estacion
):
    _, estacion_id = finca_con_estacion
    # Día previo ya sincronizado
    await sincronizar_clima_diario(pool, ProveedorFake(), fecha=date(2026, 7, 18))

    sincronizadas = await sincronizar_clima_diario(
        pool, ProveedorCaido(), fecha=date(2026, 7, 19)
    )

    assert sincronizadas == 1
    fila = await pool.fetchrow(
        "SELECT * FROM registros_clima WHERE estacion_clima_id = $1 AND fecha = $2",
        estacion_id,
        date(2026, 7, 19),
    )
    assert fila is not None
    assert fila["estimado"] is True
    assert float(fila["temp_media"]) == 25.9  # valores del último conocido


async def test_crear_scheduler_configura_cron_sin_arrancar(pool):
    scheduler = crear_scheduler(pool, proveedor=ProveedorFake())
    try:
        assert scheduler.running is False
        job = scheduler.get_job("sincronizar_clima_diario")
        assert job is not None
        trigger = job.trigger
        campos = {f.name: str(f) for f in trigger.fields}
        assert campos["hour"] == "5"
        assert campos["minute"] == "0"
        assert str(trigger.timezone) == "America/Bogota"
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
