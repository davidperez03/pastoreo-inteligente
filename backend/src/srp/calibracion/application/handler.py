"""Caso de uso: calibrar el factor de fatiga de un potrero al salir un lote.

El contexto Calibración no consulta tablas de otros contextos: reacciona al
evento de dominio `LoteSalioDePotrero` publicado en el bus en memoria (§17).
"""

from __future__ import annotations

import logging
from typing import Protocol

from srp.calibracion.domain.bayes import actualizar_factor_fatiga_bayesiano
from srp.calibracion.domain.events import LoteSalioDePotrero
from srp.shared.events import BusEventosEnMemoria, Handler
from srp.shared.types import PotreroId

logger = logging.getLogger(__name__)


class RepositorioCalibracion(Protocol):
    """Puerto de persistencia del contexto (adaptador: Postgres).

    `leer_estado` devuelve `(factor_fatiga, n_ciclos_observados,
    biomasa_predicha)` donde `biomasa_predicha` es la predicción vigente
    (`potreros.biomasa_actual_kg_ms_ha`), o `None` si el potrero no existe.
    `guardar_estado` persiste el nuevo factor y contador de ciclos.
    """

    async def leer_estado(
        self, potrero_id: PotreroId
    ) -> tuple[float, int, float | None] | None: ...

    async def guardar_estado(
        self, potrero_id: PotreroId, factor: float, n_ciclos: int
    ) -> None: ...


class CalibrarPotreroAlSalirLote:
    """Handler async de `LoteSalioDePotrero`.

    Lee la predicción vigente y el estado (factor/n_ciclos) del potrero, aplica
    la actualización bayesiana usando `biomasa_final` del evento como medición
    real, y persiste el resultado. Es responsabilidad EXCLUSIVA de este contexto
    escribir `factor_fatiga` y `n_ciclos_observados` (§17.1).
    """

    def __init__(self, repo: RepositorioCalibracion) -> None:
        self._repo = repo

    async def __call__(self, evento: LoteSalioDePotrero) -> None:
        if evento.biomasa_final is None:
            # Sin medición a la salida no hay observación con qué calibrar.
            logger.info(
                "LoteSalioDePotrero sin biomasa_final para potrero %s; no se calibra",
                evento.potrero_id,
            )
            return

        estado = await self._repo.leer_estado(evento.potrero_id)
        if estado is None:
            logger.warning(
                "Potrero %s no encontrado; no se calibra", evento.potrero_id
            )
            return

        factor_actual, n_ciclos, biomasa_predicha = estado
        if biomasa_predicha is None or biomasa_predicha <= 0:
            # Sin predicción vigente positiva no hay referencia contra la cual
            # medir el error relativo (§8); el guard del dominio lo rechazaría.
            logger.info(
                "Potrero %s sin biomasa predicha vigente; no se calibra",
                evento.potrero_id,
            )
            return

        nuevo_factor, nuevos_ciclos = actualizar_factor_fatiga_bayesiano(
            factor_actual=factor_actual,
            n_ciclos=n_ciclos,
            biomasa_predicha=biomasa_predicha,
            biomasa_medida=evento.biomasa_final,
        )
        await self._repo.guardar_estado(
            evento.potrero_id, nuevo_factor, nuevos_ciclos
        )
        logger.info(
            "Potrero %s calibrado: factor %.4f -> %.4f (ciclos %d -> %d)",
            evento.potrero_id,
            factor_actual,
            nuevo_factor,
            n_ciclos,
            nuevos_ciclos,
        )


def registrar_en_bus(bus: BusEventosEnMemoria, handler: Handler) -> None:
    """Suscribe el handler a `LoteSalioDePotrero` en el bus en memoria."""
    bus.suscribir(LoteSalioDePotrero, handler)
