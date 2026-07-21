"""Handlers de integración: estado del potrero ante eventos de pastoreo.

El contexto Ganado registra entradas/salidas y publica eventos; este contexto
es el dueño del estado del potrero (§17.1) y reacciona aquí. Corre fuera del
ciclo request (bus en memoria), como proceso del sistema — igual criterio que
los jobs de clima/NDVI.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Protocol

import asyncpg

logger = logging.getLogger(__name__)


class _EventoEntrada(Protocol):
    potrero_id: object
    fecha: date


class _EventoSalida(Protocol):
    potrero_id: object
    fecha: date


class EstadoPotreroHandler:
    """Mantiene `potreros.estado` y `fecha_ultima_salida` en sincronía con
    los eventos de pastoreo publicados por el contexto Ganado."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def al_entrar_lote(self, evento: _EventoEntrada) -> None:
        await self._pool.execute(
            "UPDATE potreros SET estado = 'ocupado' WHERE id = $1",
            evento.potrero_id,
        )
        logger.info("Potrero %s marcado ocupado", evento.potrero_id)

    async def al_salir_lote(self, evento: _EventoSalida) -> None:
        await self._pool.execute(
            """
            UPDATE potreros
            SET estado = 'descanso', fecha_ultima_salida = $2
            WHERE id = $1
            """,
            evento.potrero_id,
            evento.fecha,
        )
        logger.info("Potrero %s marcado en descanso", evento.potrero_id)
