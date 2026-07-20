"""Adaptador de clima Open-Meteo (§11, §18.4).

Implementa `ProveedorClima` contra la API pública de Open-Meteo
(https://api.open-meteo.com/v1/forecast, sin API key). Ante errores de red o
respuestas 5xx reintenta con backoff exponencial 2/4/8s (§11) antes de rendirse;
los errores 4xx se consideran definitivos y no se reintentan.

El `dormir` (por defecto `asyncio.sleep`) es inyectable para poder testear los
backoffs sin esperar tiempo real.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import date

import httpx

from srp.shared.ports import ProveedorClima
from srp.shared.types import Coordenada, RegistroClima

logger = logging.getLogger(__name__)

URL_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
VARIABLES_DIARIAS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
)
ZONA_HORARIA = "America/Bogota"

# 1 intento inicial + reintentos con backoff exponencial 2/4/8s (§11)
BACKOFFS_SEGUNDOS: tuple[float, ...] = (2.0, 4.0, 8.0)


class ErrorProveedorClima(Exception):
    """El proveedor de clima no pudo entregar datos (tras agotar reintentos)."""


class RespuestaClimaInvalida(ErrorProveedorClima):
    """La respuesta del proveedor no tiene la estructura esperada (contrato roto)."""


class OpenMeteoClimaAdapter(ProveedorClima):
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        backoffs: Sequence[float] = BACKOFFS_SEGUNDOS,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
        timeout_s: float = 15.0,
    ) -> None:
        self._client = client
        self._backoffs = tuple(backoffs)
        self._dormir = dormir
        self._timeout_s = timeout_s

    async def obtener_clima_diario(
        self, ubicacion: Coordenada, fecha: date
    ) -> RegistroClima:
        registros = await self.obtener_rango(ubicacion, fecha, fecha)
        for registro in registros:
            if registro.fecha == fecha:
                return registro
        raise RespuestaClimaInvalida(
            f"Open-Meteo no devolvió datos para {fecha.isoformat()} "
            f"en ({ubicacion.lat}, {ubicacion.lng})"
        )

    async def obtener_rango(
        self, ubicacion: Coordenada, desde: date, hasta: date
    ) -> list[RegistroClima]:
        if desde > hasta:
            raise ValueError(f"Rango inválido: desde={desde} > hasta={hasta}")
        params = {
            "latitude": ubicacion.lat,
            "longitude": ubicacion.lng,
            "daily": ",".join(VARIABLES_DIARIAS),
            "timezone": ZONA_HORARIA,
            "start_date": desde.isoformat(),
            "end_date": hasta.isoformat(),
        }
        respuesta = await self._get_con_reintentos(params)
        return _parsear_diarios(respuesta)

    async def _get_con_reintentos(self, params: dict) -> dict:
        """GET con reintentos ante error de red o 5xx; backoff 2/4/8s (§11)."""
        ultimo_error: Exception | None = None
        for intento in range(len(self._backoffs) + 1):
            if intento > 0:
                espera = self._backoffs[intento - 1]
                logger.warning(
                    "Open-Meteo falló (%s); reintento %d/%d en %.0fs",
                    ultimo_error,
                    intento,
                    len(self._backoffs),
                    espera,
                )
                await self._dormir(espera)
            try:
                resp = await self._get(params)
            except httpx.HTTPError as exc:  # errores de red/transporte/timeout
                ultimo_error = exc
                continue
            if resp.status_code >= 500:
                ultimo_error = ErrorProveedorClima(
                    f"Open-Meteo respondió {resp.status_code}"
                )
                continue
            if resp.status_code >= 400:
                # 4xx: petición malformada — reintentar no ayuda
                raise ErrorProveedorClima(
                    f"Open-Meteo rechazó la petición ({resp.status_code}): {resp.text}"
                )
            try:
                return resp.json()
            except ValueError as exc:
                raise RespuestaClimaInvalida(
                    "Open-Meteo devolvió un cuerpo que no es JSON"
                ) from exc
        raise ErrorProveedorClima(
            f"Open-Meteo no respondió tras {len(self._backoffs) + 1} intentos"
        ) from ultimo_error

    async def _get(self, params: dict) -> httpx.Response:
        if self._client is not None:
            return await self._client.get(URL_OPEN_METEO, params=params)
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            return await client.get(URL_OPEN_METEO, params=params)


def _parsear_diarios(payload: dict) -> list[RegistroClima]:
    """Convierte el bloque `daily` de Open-Meteo en registros de dominio.

    Los días sin temperatura máx/mín (nulls del proveedor) se omiten; si falta
    la media, se aproxima con (máx + mín) / 2 y precipitación nula se toma como
    0 mm.
    """
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise RespuestaClimaInvalida(
            f"Respuesta de Open-Meteo sin bloque 'daily' esperado: {list(payload)}"
        )
    fechas = daily["time"]
    columnas = {}
    for variable in VARIABLES_DIARIAS:
        valores = daily.get(variable)
        if not isinstance(valores, list) or len(valores) != len(fechas):
            raise RespuestaClimaInvalida(
                f"Serie diaria '{variable}' ausente o de longitud distinta a 'time'"
            )
        columnas[variable] = valores

    registros: list[RegistroClima] = []
    for i, fecha_iso in enumerate(fechas):
        temp_max = columnas["temperature_2m_max"][i]
        temp_min = columnas["temperature_2m_min"][i]
        if temp_max is None or temp_min is None:
            logger.warning("Open-Meteo sin temperaturas para %s; día omitido", fecha_iso)
            continue
        temp_media = columnas["temperature_2m_mean"][i]
        if temp_media is None:
            temp_media = (temp_max + temp_min) / 2
        precipitacion = columnas["precipitation_sum"][i]
        registros.append(
            RegistroClima(
                fecha=date.fromisoformat(fecha_iso),
                temp_media=float(temp_media),
                temp_max=float(temp_max),
                temp_min=float(temp_min),
                precipitacion_mm=float(precipitacion) if precipitacion is not None else 0.0,
                estimado=False,
            )
        )
    return registros
