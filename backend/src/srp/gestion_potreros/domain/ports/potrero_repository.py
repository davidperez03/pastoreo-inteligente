"""Puerto de salida: repositorio del agregado Potrero (§18.2)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from srp.gestion_potreros.domain.entities import Potrero
from srp.shared.types import FincaId, PotreroId


class PotreroRepository(ABC):
    @abstractmethod
    async def guardar(self, potrero: Potrero) -> None: ...

    @abstractmethod
    async def obtener(self, id: PotreroId) -> Potrero | None: ...

    @abstractmethod
    async def listar_por_finca(self, finca_id: FincaId) -> list[Potrero]: ...
