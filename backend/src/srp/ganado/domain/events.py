"""Eventos de dominio del contexto Gestión de Ganado (§17.3).

ATENCIÓN: las firmas de estos eventos son un contrato público — otros
contextos (Gestión de Potreros, Modelado Agronómico, Rotación) se suscriben
a ellos por el bus. No cambiar nombres, orden ni tipos de los campos sin
coordinar con los consumidores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from srp.shared.events import DomainEvent
from srp.shared.types import LoteId, PotreroId


@dataclass(frozen=True)
class LoteEntroAPotrero(DomainEvent):
    """Un lote entró a pastorear en un potrero."""

    potrero_id: PotreroId
    lote_id: LoteId
    fecha: date
    biomasa_inicial: float | None


@dataclass(frozen=True)
class LoteSalioDePotrero(DomainEvent):
    """Un lote salió de un potrero (fin del ciclo de ocupación)."""

    potrero_id: PotreroId
    lote_id: LoteId | None
    fecha: date
    biomasa_inicial: float | None
    biomasa_final: float | None
