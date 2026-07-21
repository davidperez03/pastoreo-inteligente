"""Eventos de dominio locales del contexto Modelado Agronómico (§17.3).

Heredan del `DomainEvent` del shared kernel para poder viajar por el bus de
eventos en memoria sin acoplar el dominio a la infraestructura.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from srp.shared.events import DomainEvent
from srp.shared.types import PotreroId


@dataclass(frozen=True)
class BiomasaRecalculada(DomainEvent):
    """La estimación de biomasa de un potrero cambió.

    `fuente` indica qué paso la produjo: "modelo" (predicción con clima) o
    "kalman" (corrección con NDVI). El contexto de Rotación se suscribe para
    saber cuándo un potrero cambia de disponibilidad.
    """

    potrero_id: PotreroId
    fecha: date
    biomasa_kg_ms_ha: float
    fuente: str  # "modelo" | "kalman"
