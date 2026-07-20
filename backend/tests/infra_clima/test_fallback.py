"""Tests del fallback de último-conocido (§11) contra Postgres real."""

from __future__ import annotations

from datetime import date

import pytest

from srp.agronomia.infra_clima.fallback import SinDatosClima, clima_con_fallback
from srp.agronomia.infra_clima.repositorio_clima import guardar_registros
from srp.shared.ports import ProveedorClima
from srp.shared.types import Coordenada, RegistroClima

YOPAL = Coordenada(lat=5.3378, lng=-72.3959)


class ProveedorSiempreFalla(ProveedorClima):
    async def obtener_clima_diario(
        self, ubicacion: Coordenada, fecha: date
    ) -> RegistroClima:
        raise ConnectionError("proveedor caído tras agotar reintentos")


class ProveedorFijo(ProveedorClima):
    def __init__(self, registro: RegistroClima) -> None:
        self.registro = registro

    async def obtener_clima_diario(
        self, ubicacion: Coordenada, fecha: date
    ) -> RegistroClima:
        return self.registro


async def test_proveedor_caido_devuelve_ultimo_conocido_estimado(pool, estacion):
    conocido = RegistroClima(
        fecha=date(2026, 7, 18),
        temp_media=25.1,
        temp_max=29.8,
        temp_min=21.7,
        precipitacion_mm=18.7,
    )
    await guardar_registros(pool, estacion, [conocido])

    resultado = await clima_con_fallback(
        ProveedorSiempreFalla(), pool, estacion, YOPAL, date(2026, 7, 19)
    )

    assert resultado.estimado is True
    assert resultado.fecha == date(2026, 7, 19)
    # Valores del último registro conocido
    assert resultado.temp_media == 25.1
    assert resultado.temp_max == 29.8
    assert resultado.temp_min == 21.7
    assert resultado.precipitacion_mm == 18.7


async def test_proveedor_caido_sin_historico_lanza_error_claro(pool, estacion):
    with pytest.raises(SinDatosClima):
        await clima_con_fallback(
            ProveedorSiempreFalla(), pool, estacion, YOPAL, date(2026, 7, 19)
        )


async def test_proveedor_sano_no_activa_fallback(pool, estacion):
    real = RegistroClima(
        fecha=date(2026, 7, 19),
        temp_media=25.9,
        temp_max=30.6,
        temp_min=22.4,
        precipitacion_mm=0.0,
    )

    resultado = await clima_con_fallback(
        ProveedorFijo(real), pool, estacion, YOPAL, date(2026, 7, 19)
    )

    assert resultado == real
    assert resultado.estimado is False
