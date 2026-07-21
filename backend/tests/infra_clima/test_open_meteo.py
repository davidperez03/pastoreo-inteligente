"""Contract tests del adaptador Open-Meteo (respuesta grabada + respx, §14)."""

from __future__ import annotations

import os
from datetime import date

import httpx
import pytest
import respx

from srp.agronomia.infra_clima.open_meteo import (
    URL_OPEN_METEO,
    ErrorProveedorClima,
    OpenMeteoClimaAdapter,
    RespuestaClimaInvalida,
)
from srp.shared.types import Coordenada, RegistroClima

YOPAL = Coordenada(lat=5.3378, lng=-72.3959)


class RelojFake:
    """Sustituto inyectable de asyncio.sleep que registra los backoffs."""

    def __init__(self) -> None:
        self.esperas: list[float] = []

    async def __call__(self, segundos: float) -> None:
        self.esperas.append(segundos)


@respx.mock
async def test_obtener_rango_parsea_respuesta_grabada(respuesta_open_meteo):
    ruta = respx.get(URL_OPEN_METEO).mock(
        return_value=httpx.Response(200, json=respuesta_open_meteo)
    )
    adaptador = OpenMeteoClimaAdapter()

    registros = await adaptador.obtener_rango(
        YOPAL, date(2026, 7, 17), date(2026, 7, 19)
    )

    assert len(registros) == 3
    primero = registros[0]
    assert isinstance(primero, RegistroClima)
    assert primero.fecha == date(2026, 7, 17)
    assert primero.temp_max == 31.4
    assert primero.temp_min == 22.1
    assert primero.temp_media == 26.2
    assert primero.precipitacion_mm == 4.2
    assert primero.humedad_suelo_pct is None
    assert primero.estimado is False
    assert [r.fecha for r in registros] == [
        date(2026, 7, 17),
        date(2026, 7, 18),
        date(2026, 7, 19),
    ]

    params = ruta.calls.last.request.url.params
    assert params["latitude"] == str(YOPAL.lat)
    assert params["longitude"] == str(YOPAL.lng)
    assert params["timezone"] == "America/Bogota"
    assert params["start_date"] == "2026-07-17"
    assert params["end_date"] == "2026-07-19"
    assert set(params["daily"].split(",")) == {
        "temperature_2m_max",
        "temperature_2m_min",
        "temperature_2m_mean",
        "precipitation_sum",
    }


@respx.mock
async def test_obtener_clima_diario_devuelve_el_dia_pedido(respuesta_open_meteo):
    # Respuesta de un solo día, como cuando start_date == end_date
    un_dia = dict(respuesta_open_meteo)
    un_dia["daily"] = {
        "time": ["2026-07-19"],
        "temperature_2m_max": [30.6],
        "temperature_2m_min": [22.4],
        "temperature_2m_mean": [25.9],
        "precipitation_sum": [0.0],
    }
    respx.get(URL_OPEN_METEO).mock(return_value=httpx.Response(200, json=un_dia))

    registro = await OpenMeteoClimaAdapter().obtener_clima_diario(
        YOPAL, date(2026, 7, 19)
    )

    assert registro.fecha == date(2026, 7, 19)
    assert registro.temp_media == 25.9
    assert registro.precipitacion_mm == 0.0
    assert registro.estimado is False


@respx.mock
async def test_reintenta_ante_5xx_y_luego_exito(respuesta_open_meteo):
    ruta = respx.get(URL_OPEN_METEO).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(503),
            httpx.Response(200, json=respuesta_open_meteo),
        ]
    )
    reloj = RelojFake()
    adaptador = OpenMeteoClimaAdapter(dormir=reloj)

    registros = await adaptador.obtener_rango(
        YOPAL, date(2026, 7, 17), date(2026, 7, 19)
    )

    assert len(registros) == 3
    assert ruta.call_count == 3
    # Backoff exponencial §11: 2s tras el primer fallo, 4s tras el segundo
    assert reloj.esperas == [2.0, 4.0]


@respx.mock
async def test_agota_reintentos_ante_error_de_red_persistente():
    ruta = respx.get(URL_OPEN_METEO).mock(
        side_effect=httpx.ConnectError("red caída")
    )
    reloj = RelojFake()
    adaptador = OpenMeteoClimaAdapter(dormir=reloj)

    with pytest.raises(ErrorProveedorClima):
        await adaptador.obtener_clima_diario(YOPAL, date(2026, 7, 19))

    # 1 intento inicial + 3 reintentos con backoff 2/4/8s (§11)
    assert ruta.call_count == 4
    assert reloj.esperas == [2.0, 4.0, 8.0]


@respx.mock
async def test_4xx_no_se_reintenta():
    ruta = respx.get(URL_OPEN_METEO).mock(
        return_value=httpx.Response(400, text="Invalid latitude")
    )
    reloj = RelojFake()

    with pytest.raises(ErrorProveedorClima):
        await OpenMeteoClimaAdapter(dormir=reloj).obtener_clima_diario(
            YOPAL, date(2026, 7, 19)
        )

    assert ruta.call_count == 1
    assert reloj.esperas == []


@respx.mock
async def test_contrato_roto_lanza_respuesta_invalida():
    respx.get(URL_OPEN_METEO).mock(
        return_value=httpx.Response(200, json={"hourly": {}})
    )

    with pytest.raises(RespuestaClimaInvalida):
        await OpenMeteoClimaAdapter().obtener_clima_diario(YOPAL, date(2026, 7, 19))


@respx.mock
async def test_dia_sin_temperaturas_se_omite(respuesta_open_meteo):
    con_nulls = dict(respuesta_open_meteo)
    con_nulls["daily"] = {
        "time": ["2026-07-18", "2026-07-19"],
        "temperature_2m_max": [None, 30.6],
        "temperature_2m_min": [21.7, 22.4],
        "temperature_2m_mean": [None, None],
        "precipitation_sum": [18.7, None],
    }
    respx.get(URL_OPEN_METEO).mock(return_value=httpx.Response(200, json=con_nulls))

    registros = await OpenMeteoClimaAdapter().obtener_rango(
        YOPAL, date(2026, 7, 18), date(2026, 7, 19)
    )

    assert len(registros) == 1
    unico = registros[0]
    assert unico.fecha == date(2026, 7, 19)
    # media ausente → aproximada con (máx + mín) / 2; precipitación null → 0
    assert unico.temp_media == pytest.approx((30.6 + 22.4) / 2)
    assert unico.precipitacion_mm == 0.0


@pytest.mark.skipif(
    not os.environ.get("SRP_E2E_RED"),
    reason="requiere red real (exporta SRP_E2E_RED=1 para habilitarlo)",
)
async def test_e2e_contra_api_real():
    from datetime import timedelta

    ayer = date.today() - timedelta(days=1)
    registro = await OpenMeteoClimaAdapter().obtener_clima_diario(YOPAL, ayer)

    assert registro.fecha == ayer
    assert -10.0 < registro.temp_min <= registro.temp_max < 50.0
    assert registro.precipitacion_mm >= 0.0
