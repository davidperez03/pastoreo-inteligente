"""Puerto de salida: persistencia de eventos de pastoreo (§18.2).

Un "evento de pastoreo" es la fila histórica de ocupación de un potrero por
un lote (tabla `eventos_pastoreo`, §2): se abre con la entrada y se cierra
con la salida.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date

from srp.ganado.domain.entities import EventoPastoreo
from srp.shared.types import LoteId, PotreroId


class EventosPastoreoRepository(ABC):
    @abstractmethod
    async def abrir_evento(
        self,
        lote_id: LoteId,
        potrero_id: PotreroId,
        fecha_entrada: date,
        biomasa_inicial: float | None,
    ) -> EventoPastoreo:
        """Crea la fila de ocupación (fecha_salida NULL) y la devuelve."""

    @abstractmethod
    async def cerrar_evento(
        self,
        evento_id: uuid.UUID,
        fecha_salida: date,
        biomasa_final: float | None,
    ) -> EventoPastoreo:
        """Cierra la fila con fecha_salida y biomasa_final; la devuelve."""

    @abstractmethod
    async def evento_abierto_de_lote(self, lote_id: LoteId) -> EventoPastoreo | None:
        """La ocupación abierta (fecha_salida IS NULL) del lote, si existe."""
