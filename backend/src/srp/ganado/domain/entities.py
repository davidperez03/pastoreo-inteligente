"""Agregados y entidades del contexto Gestión de Ganado (§17.2).

Dominio puro: sin FastAPI, sin asyncpg, sin SQL. La única dependencia externa
permitida es el shared kernel (`srp.shared`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from srp.ganado.domain.errors import DomainError
from srp.ganado.domain.events import LoteEntroAPotrero, LoteSalioDePotrero
from srp.shared.events import DomainEvent
from srp.shared.types import FincaId, LoteId, PotreroId

# Peso de referencia de una Unidad Animal (vaca adulta de 450 kg).
KG_POR_UNIDAD_ANIMAL = 450.0


@dataclass(frozen=True)
class EventoPastoreo:
    """Registro (entidad de solo lectura para el dominio) de una ocupación
    de potrero por un lote. La fila viva se persiste en `eventos_pastoreo`."""

    id: uuid.UUID
    lote_id: LoteId
    potrero_id: PotreroId
    fecha_entrada: date
    fecha_salida: date | None = None
    biomasa_inicial: float | None = None
    biomasa_final: float | None = None

    @property
    def abierto(self) -> bool:
        return self.fecha_salida is None


class LoteGanado:
    """Aggregate root del lote de ganado.

    Invariantes:
    - n_animales > 0 y peso_promedio_kg > 0 (espejo de los CHECK de §2).
    - Un lote está a lo sumo en un potrero a la vez (`potrero_actual_id`).

    Decisión documentada — entrada estando ya en un potrero: se lanza
    `DomainError` en vez de registrar una salida implícita. Una salida
    implícita necesitaría inventar la biomasa final del potrero anterior
    (dato agronómico que alimenta la calibración de fatiga, §8) y ocultaría
    errores del operador; el flujo correcto es registrar la salida explícita
    primero.
    """

    def __init__(
        self,
        id: LoteId,
        finca_id: FincaId,
        nombre: str | None,
        n_animales: int,
        peso_promedio_kg: float,
        potrero_actual_id: PotreroId | None = None,
        biomasa_inicial_actual: float | None = None,
    ) -> None:
        if n_animales <= 0:
            raise DomainError("n_animales debe ser mayor que 0")
        if peso_promedio_kg <= 0:
            raise DomainError("peso_promedio_kg debe ser mayor que 0")
        self._id = id
        self._finca_id = finca_id
        self._nombre = nombre
        self._n_animales = n_animales
        self._peso_promedio_kg = float(peso_promedio_kg)
        self._potrero_actual_id = potrero_actual_id
        # Biomasa inicial del ciclo de ocupación en curso (si lo hay); viaja
        # en LoteSalioDePotrero para que los consumidores calculen consumo.
        self._biomasa_inicial_actual = biomasa_inicial_actual
        self._eventos: list[DomainEvent] = []

    # --- identidad y estado ---

    @property
    def id(self) -> LoteId:
        return self._id

    @property
    def finca_id(self) -> FincaId:
        return self._finca_id

    @property
    def nombre(self) -> str | None:
        return self._nombre

    @property
    def n_animales(self) -> int:
        return self._n_animales

    @property
    def peso_promedio_kg(self) -> float:
        return self._peso_promedio_kg

    @property
    def potrero_actual_id(self) -> PotreroId | None:
        return self._potrero_actual_id

    @property
    def biomasa_inicial_actual(self) -> float | None:
        return self._biomasa_inicial_actual

    @property
    def ua_equivalente(self) -> float:
        """Unidades Animal: n_animales × peso_promedio / 450 (espejo de la
        columna generada de `lotes_ganado`, §2)."""
        return self._n_animales * self._peso_promedio_kg / KG_POR_UNIDAD_ANIMAL

    # --- comportamiento ---

    def entrar_a_potrero(
        self,
        potrero_id: PotreroId,
        fecha: date,
        biomasa_inicial: float | None = None,
    ) -> None:
        """Registra la entrada del lote a un potrero y emite LoteEntroAPotrero.

        Lanza DomainError si el lote ya está en un potrero (ver decisión
        documentada en el docstring de la clase).
        """
        if self._potrero_actual_id is not None:
            raise DomainError(
                f"El lote ya está en el potrero {self._potrero_actual_id}; "
                "registre la salida antes de una nueva entrada"
            )
        self._potrero_actual_id = potrero_id
        self._biomasa_inicial_actual = biomasa_inicial
        self._eventos.append(
            LoteEntroAPotrero(
                potrero_id=potrero_id,
                lote_id=self._id,
                fecha=fecha,
                biomasa_inicial=biomasa_inicial,
            )
        )

    def salir_de_potrero(self, fecha: date, biomasa_final: float | None = None) -> None:
        """Registra la salida del lote de su potrero actual y emite
        LoteSalioDePotrero. Lanza DomainError si no está en ningún potrero."""
        if self._potrero_actual_id is None:
            raise DomainError("El lote no está en ningún potrero")
        potrero_id = self._potrero_actual_id
        self._potrero_actual_id = None
        biomasa_inicial = self._biomasa_inicial_actual
        self._biomasa_inicial_actual = None
        self._eventos.append(
            LoteSalioDePotrero(
                potrero_id=potrero_id,
                lote_id=self._id,
                fecha=fecha,
                biomasa_inicial=biomasa_inicial,
                biomasa_final=biomasa_final,
            )
        )

    # --- eventos de dominio ---

    def eventos_pendientes(self) -> list[DomainEvent]:
        return list(self._eventos)

    def limpiar_eventos(self) -> None:
        self._eventos.clear()
