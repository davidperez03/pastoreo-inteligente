"""Puertos cross-contexto del shared kernel (§18.2).

Solo viven aquí los puertos cuya implementación y consumo cruzan fronteras de
contexto (o que varios contextos necesitan conocer). Los puertos internos de un
contexto (p. ej. PotreroRepository) viven en `<contexto>/domain/ports/` según
la estructura de §18.1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from srp.shared.events import DomainEvent
from srp.shared.types import (
    Calendario,
    Coordenada,
    LecturaNdvi,
    LoteSnapshot,
    PotreroSnapshot,
    RegistroClima,
)


class PublicadorEventos(ABC):
    @abstractmethod
    async def publicar(self, eventos: list[DomainEvent]) -> None: ...


class ProveedorClima(ABC):
    @abstractmethod
    async def obtener_clima_diario(
        self, ubicacion: Coordenada, fecha: date
    ) -> RegistroClima: ...


class ProveedorNdvi(ABC):
    @abstractmethod
    async def obtener_ndvi(
        self, poligono_geojson: dict, fecha: date
    ) -> LecturaNdvi: ...


class OptimizadorRotacion(ABC):
    @abstractmethod
    def optimizar(
        self,
        potreros: list[PotreroSnapshot],
        lotes: list[LoteSnapshot],
        horizonte_dias: int,
    ) -> Calendario: ...


class GeometriaValidator(ABC):
    """Construye y valida un polígono a partir de puntos WGS84 (§3.4).

    Devuelve un dict con: geojson, area_ha, n_puntos, advertencia (str | None).
    """

    @abstractmethod
    def construir_y_validar(
        self, puntos: list[tuple[float, float]]
    ) -> dict: ...
