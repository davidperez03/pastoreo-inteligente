"""Handlers de integración: estado del potrero ante eventos de pastoreo.

El contexto Ganado registra entradas/salidas y publica eventos; este contexto
es el dueño del estado del potrero (§17.1) y reacciona aquí. Corre dentro del
proceso de la API (bus en memoria wireado en el lifespan de app.py), no en el
worker — la diferencia importa para la RLS: a diferencia de los jobs del
worker (que sí operan intencionalmente sobre todas las organizaciones), esta
escritura reacciona a un evento de UNA organización concreta, así que debe
pasar por `conexion_org` como cualquier escritura de dominio — el pool de la
API conecta con un rol sin BYPASSRLS (§10, §19.3), y una escritura sin
organización fijada no fallaría con error, simplemente no afectaría ninguna
fila (silencioso y mucho peor que un error).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Protocol

import asyncpg

from srp.shared.db import conexion_org

logger = logging.getLogger(__name__)


class _EventoEntrada(Protocol):
    potrero_id: object
    fecha: date


class _EventoSalida(Protocol):
    potrero_id: object
    fecha: date


class PotreroSinOrganizacion(LookupError):
    """El potrero del evento no resuelve a ninguna organización (borrado
    entre el evento y el handler, o dato inconsistente)."""


class EstadoPotreroHandler:
    """Mantiene `potreros.estado` y `fecha_ultima_salida` en sincronía con
    los eventos de pastoreo publicados por el contexto Ganado."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _organizacion_del_potrero(self, potrero_id: object):
        # El evento solo trae potrero_id; resolvemos la organización dueña
        # antes de escribir, para poder fijar app.current_org y que la
        # escritura pase la política RLS (§2) igual que cualquier otra.
        # Vía la función SECURITY DEFINER (migración 0004): una consulta
        # normal aquí no vería nada, porque potreros/fincas también tienen
        # RLS y aún no sabemos qué organización fijar — es precisamente lo
        # que esta función resuelve sin bypasear RLS para el resto del rol.
        org_id = await self._pool.fetchval(
            "SELECT organizacion_de_potrero($1)", potrero_id
        )
        if org_id is None:
            raise PotreroSinOrganizacion(str(potrero_id))
        return org_id

    async def al_entrar_lote(self, evento: _EventoEntrada) -> None:
        try:
            org_id = await self._organizacion_del_potrero(evento.potrero_id)
        except PotreroSinOrganizacion:
            logger.warning(
                "Potrero %s sin organización resoluble; no se actualiza estado",
                evento.potrero_id,
            )
            return
        async with conexion_org(self._pool, org_id) as con:
            await con.execute(
                "UPDATE potreros SET estado = 'ocupado' WHERE id = $1",
                evento.potrero_id,
            )
        logger.info("Potrero %s marcado ocupado", evento.potrero_id)

    async def al_salir_lote(self, evento: _EventoSalida) -> None:
        try:
            org_id = await self._organizacion_del_potrero(evento.potrero_id)
        except PotreroSinOrganizacion:
            logger.warning(
                "Potrero %s sin organización resoluble; no se actualiza estado",
                evento.potrero_id,
            )
            return
        async with conexion_org(self._pool, org_id) as con:
            await con.execute(
                """
                UPDATE potreros
                SET estado = 'descanso', fecha_ultima_salida = $2
                WHERE id = $1
                """,
                evento.potrero_id,
                evento.fecha,
            )
        logger.info("Potrero %s marcado en descanso", evento.potrero_id)
