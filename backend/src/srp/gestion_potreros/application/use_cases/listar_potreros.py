"""Casos de uso de consulta: listar potreros de una finca y obtener uno."""

from __future__ import annotations

from srp.gestion_potreros.application.dto import PotreroDTO, potrero_a_dto
from srp.gestion_potreros.domain.ports.potrero_repository import PotreroRepository
from srp.shared.types import FincaId, PotreroId


class ListarPotreros:
    def __init__(self, repo: PotreroRepository) -> None:
        self._repo = repo

    async def ejecutar(self, finca_id: FincaId) -> list[PotreroDTO]:
        potreros = await self._repo.listar_por_finca(finca_id)
        return [potrero_a_dto(p) for p in potreros]


class ObtenerPotrero:
    def __init__(self, repo: PotreroRepository) -> None:
        self._repo = repo

    async def ejecutar(self, potrero_id: PotreroId) -> PotreroDTO | None:
        potrero = await self._repo.obtener(potrero_id)
        return potrero_a_dto(potrero) if potrero is not None else None
