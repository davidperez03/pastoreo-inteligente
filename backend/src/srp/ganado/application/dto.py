"""DTOs de la capa de aplicación (§18.1): proyecciones planas de los
agregados para los adaptadores de entrada; nunca se expone el agregado."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from srp.ganado.domain.entities import EventoPastoreo, LoteGanado


@dataclass(frozen=True)
class LoteDTO:
    id: uuid.UUID
    finca_id: uuid.UUID
    nombre: str | None
    n_animales: int
    peso_promedio_kg: float
    ua_equivalente: float
    potrero_actual_id: uuid.UUID | None

    @classmethod
    def desde_agregado(cls, lote: LoteGanado) -> LoteDTO:
        return cls(
            id=lote.id,
            finca_id=lote.finca_id,
            nombre=lote.nombre,
            n_animales=lote.n_animales,
            peso_promedio_kg=lote.peso_promedio_kg,
            ua_equivalente=lote.ua_equivalente,
            potrero_actual_id=lote.potrero_actual_id,
        )


@dataclass(frozen=True)
class EventoPastoreoDTO:
    id: uuid.UUID
    lote_id: uuid.UUID
    potrero_id: uuid.UUID
    fecha_entrada: date
    fecha_salida: date | None
    biomasa_inicial: float | None
    biomasa_final: float | None

    @classmethod
    def desde_entidad(cls, evento: EventoPastoreo) -> EventoPastoreoDTO:
        return cls(
            id=evento.id,
            lote_id=evento.lote_id,
            potrero_id=evento.potrero_id,
            fecha_entrada=evento.fecha_entrada,
            fecha_salida=evento.fecha_salida,
            biomasa_inicial=evento.biomasa_inicial,
            biomasa_final=evento.biomasa_final,
        )
