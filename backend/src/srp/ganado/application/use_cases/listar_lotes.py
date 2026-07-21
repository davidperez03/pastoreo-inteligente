"""Caso de uso: listar los lotes de una finca."""

from __future__ import annotations

from srp.ganado.application.dto import LoteDTO
from srp.ganado.domain.ports.lote_repository import LoteRepository
from srp.shared.types import FincaId


class ListarLotes:
    def __init__(self, lotes: LoteRepository) -> None:
        self._lotes = lotes

    async def ejecutar(self, finca_id: FincaId) -> list[LoteDTO]:
        return [
            LoteDTO.desde_agregado(lote)
            for lote in await self._lotes.listar_por_finca(finca_id)
        ]
