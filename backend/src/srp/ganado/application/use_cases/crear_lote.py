"""Caso de uso: crear un lote de ganado."""

from __future__ import annotations

import uuid

from srp.ganado.application.dto import LoteDTO
from srp.ganado.domain.entities import LoteGanado
from srp.ganado.domain.ports.lote_repository import LoteRepository
from srp.shared.types import FincaId, LoteId


class CrearLote:
    def __init__(self, lotes: LoteRepository) -> None:
        self._lotes = lotes

    async def ejecutar(
        self,
        finca_id: FincaId,
        nombre: str | None,
        n_animales: int,
        peso_promedio_kg: float,
    ) -> LoteDTO:
        lote = LoteGanado(
            id=LoteId(uuid.uuid4()),
            finca_id=finca_id,
            nombre=nombre,
            n_animales=n_animales,
            peso_promedio_kg=peso_promedio_kg,
        )
        await self._lotes.guardar(lote)
        return LoteDTO.desde_agregado(lote)
