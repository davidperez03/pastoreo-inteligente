"""Eventos de dominio del contexto Gestión de Potreros (§17.3).

`LoteSalioDePotrero` es contrato de integración: los contextos de Calibración
y Modelado Agronómico se suscriben a él. Su firma no debe cambiar sin
coordinarlo con esos contextos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from srp.shared.events import DomainEvent
from srp.shared.types import LoteId, PotreroId


@dataclass(frozen=True)
class PotreroLevantado(DomainEvent):
    potrero_id: PotreroId
    area_ha: float
    metodo: str


@dataclass(frozen=True)
class LoteSalioDePotrero(DomainEvent):
    potrero_id: PotreroId
    lote_id: LoteId | None
    fecha: date
    biomasa_inicial: float | None
    biomasa_final: float | None
