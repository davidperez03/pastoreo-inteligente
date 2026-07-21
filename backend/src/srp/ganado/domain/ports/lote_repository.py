"""Puerto de salida: persistencia de lotes de ganado (§18.2)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from srp.ganado.domain.entities import LoteGanado
from srp.shared.types import FincaId, LoteId


class LoteRepository(ABC):
    @abstractmethod
    async def guardar(self, lote: LoteGanado) -> None:
        """Inserta o actualiza el lote (upsert por id)."""

    @abstractmethod
    async def obtener(self, lote_id: LoteId) -> LoteGanado | None:
        """Devuelve el lote o None si no existe (o no es visible por RLS)."""

    @abstractmethod
    async def listar_por_finca(self, finca_id: FincaId) -> list[LoteGanado]:
        """Lotes de una finca."""
