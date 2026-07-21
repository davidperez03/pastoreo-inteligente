"""Eventos de dominio consumidos por el contexto Calibración (§17.3).

`LoteSalioDePotrero` la PUBLICA otro contexto (Gestión de Ganado / Rotación).
Aquí se define LOCALMENTE con la firma acordada para no importar de otro
contexto (§17.1: ningún contexto importa el código interno de otro). En la fase
de integración se unificará en una única clase del shared kernel; mientras
tanto ambas definiciones deben mantener EXACTAMENTE la misma firma para que el
bus en memoria haga match por tipo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from srp.shared.events import DomainEvent
from srp.shared.types import LoteId, PotreroId


@dataclass(frozen=True)
class LoteSalioDePotrero(DomainEvent):
    """Un lote abandonó un potrero; cierra un ciclo de pastoreo.

    `biomasa_final` es la biomasa remanente medida a la salida y es la
    observación con la que se calibra el factor de fatiga del potrero.
    Puede venir `None` cuando no hubo medición: en ese caso no se calibra.
    """

    potrero_id: PotreroId
    lote_id: LoteId | None
    fecha: date
    biomasa_inicial: float | None
    biomasa_final: float | None
