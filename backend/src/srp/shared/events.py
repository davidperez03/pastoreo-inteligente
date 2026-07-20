"""Eventos de dominio y bus en memoria (§17.3).

El bus en memoria es el mecanismo de integración entre contextos en la etapa
de monolito modular: ningún contexto hace SELECT/JOIN sobre tablas de otro;
se suscribe a eventos. Reemplazarlo por una cola real (§19.2) es un cambio de
adaptador, no de dominio.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainEvent:
    """Base de todos los eventos de dominio. Subclases: dataclasses frozen."""


Handler = Callable[[DomainEvent], Awaitable[None] | None]


class BusEventosEnMemoria:
    """Implementación en memoria del puerto PublicadorEventos.

    Un handler que falla no debe tumbar al publicador ni a los demás handlers:
    se registra el error y se continúa (el evento ya ocurrió en el dominio).
    """

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def suscribir(self, tipo_evento: type[DomainEvent], handler: Handler) -> None:
        self._handlers[tipo_evento].append(handler)

    async def publicar(self, eventos: list[DomainEvent]) -> None:
        for evento in eventos:
            for handler in self._handlers[type(evento)]:
                try:
                    resultado = handler(evento)
                    if asyncio.iscoroutine(resultado):
                        await resultado
                except Exception:
                    logger.exception(
                        "Handler %r falló procesando %r", handler, evento
                    )
