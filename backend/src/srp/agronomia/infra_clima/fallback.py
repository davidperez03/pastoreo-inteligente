"""Fallback de último-conocido para el clima (§11).

Si el proveedor externo falla incluso tras sus reintentos con backoff, el
cálculo agronómico no se detiene: se usa el último registro conocido de la
estación marcado `estimado=True`. Solo si tampoco hay histórico se propaga un
error claro.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import date

import asyncpg

from srp.agronomia.infra_clima.repositorio_clima import ultimo_registro
from srp.shared.ports import ProveedorClima
from srp.shared.types import Coordenada, RegistroClima

logger = logging.getLogger(__name__)


class SinDatosClima(Exception):
    """No hay dato del proveedor ni registro histórico para la estación."""


async def clima_con_fallback(
    proveedor: ProveedorClima,
    pool: asyncpg.Pool,
    estacion_id: uuid.UUID,
    ubicacion: Coordenada,
    fecha: date,
) -> RegistroClima:
    """Clima de `fecha` para la estación, degradando a último-conocido (§11).

    Devuelve el dato real del proveedor si responde; si falla, el último
    registro persistido reetiquetado con la fecha pedida y `estimado=True`.
    Lanza `SinDatosClima` si no hay ni proveedor ni histórico.
    """
    try:
        return await proveedor.obtener_clima_diario(ubicacion, fecha)
    except Exception as exc:
        logger.warning(
            "Proveedor de clima falló para estación %s (%s); "
            "aplicando fallback de último-conocido",
            estacion_id,
            exc,
        )
        ultimo = await ultimo_registro(pool, estacion_id)
        if ultimo is None:
            raise SinDatosClima(
                f"Sin clima para la estación {estacion_id} en {fecha.isoformat()}: "
                "el proveedor falló y no existe ningún registro histórico "
                "para usar como fallback"
            ) from exc
        return dataclasses.replace(ultimo, fecha=fecha, estimado=True)
