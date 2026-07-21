"""Caso de uso: registrar un potrero levantado manualmente (§18.3).

Recibe la lista de puntos (lat, lng) ya normalizada en el command. Solo
depende de puertos: `PotreroRepository`, `GeometriaValidator` (shared kernel)
y `PublicadorEventos`.
"""

from __future__ import annotations

from srp.gestion_potreros.application.dto import (
    PotreroDTO,
    RegistrarPotreroManualCommand,
    potrero_a_dto,
)
from srp.gestion_potreros.domain.entities import Potrero
from srp.gestion_potreros.domain.ports.potrero_repository import PotreroRepository
from srp.gestion_potreros.domain.value_objects import Geometria
from srp.shared.ports import GeometriaValidator, PublicadorEventos
from srp.shared.types import Coordenada


class RegistrarPotreroManual:
    def __init__(
        self,
        repo: PotreroRepository,
        validador: GeometriaValidator,
        eventos: PublicadorEventos,
    ) -> None:
        self._repo = repo
        self._validador = validador
        self._eventos = eventos

    async def ejecutar(self, cmd: RegistrarPotreroManualCommand) -> PotreroDTO:
        resultado = self._validador.construir_y_validar(list(cmd.puntos))

        geometria = Geometria(
            puntos=tuple(Coordenada(lat=lat, lng=lng) for lat, lng in cmd.puntos),
            metodo_levantamiento=cmd.metodo_levantamiento,
            accuracy_m=cmd.accuracy_m,
        )
        potrero = Potrero.crear(
            finca_id=cmd.finca_id,
            nombre=cmd.nombre,
            geometria=geometria,
            geojson=resultado["geojson"],
            area_ha=resultado["area_ha"],
            especie_pasto_id=cmd.especie_pasto_id,
            tipo_suelo=cmd.tipo_suelo,
            fuente_agua=cmd.fuente_agua,
        )
        await self._repo.guardar(potrero)
        await self._eventos.publicar(potrero.eventos_pendientes())
        potrero.limpiar_eventos()
        return potrero_a_dto(potrero, advertencia=resultado.get("advertencia"))
