"""Caso de uso: importar un potrero desde planimetría ya convertida a GeoJSON
(§18.3).

NO parsea archivos GPX/DXF/KML: eso es responsabilidad del paquete de
planimetría (otra unidad), que se integra después entregando aquí un GeoJSON
Polygon en WGS84.
"""

from __future__ import annotations

from srp.gestion_potreros.application.dto import (
    ImportarPlanimetriaCommand,
    PotreroDTO,
    potrero_a_dto,
)
from srp.gestion_potreros.domain.entities import Potrero
from srp.gestion_potreros.domain.ports.potrero_repository import PotreroRepository
from srp.gestion_potreros.domain.value_objects import Geometria
from srp.shared.ports import GeometriaValidator, PublicadorEventos
from srp.shared.types import Coordenada


def puntos_desde_geojson(geojson: dict) -> list[tuple[float, float]]:
    """Extrae el anillo exterior de un Polygon GeoJSON como puntos (lat, lng).

    Acepta una geometría `Polygon` directa o un `Feature` que la contenga.
    GeoJSON ordena las coordenadas como [lng, lat]; aquí se devuelven (lat, lng),
    la convención del resto del contexto.
    """
    geometria = geojson.get("geometry", geojson)
    if geometria.get("type") != "Polygon":
        raise ValueError(
            f"Se esperaba un GeoJSON Polygon, llegó {geometria.get('type')!r}"
        )
    try:
        anillo_exterior = geometria["coordinates"][0]
    except (KeyError, IndexError) as exc:
        raise ValueError("GeoJSON Polygon sin anillo de coordenadas") from exc
    puntos = [(float(lat), float(lng)) for lng, lat, *_ in anillo_exterior]
    # El anillo GeoJSON viene cerrado (primer punto repetido al final)
    if len(puntos) > 1 and puntos[0] == puntos[-1]:
        puntos = puntos[:-1]
    return puntos


class ImportarPlanimetria:
    def __init__(
        self,
        repo: PotreroRepository,
        validador: GeometriaValidator,
        eventos: PublicadorEventos,
    ) -> None:
        self._repo = repo
        self._validador = validador
        self._eventos = eventos

    async def ejecutar(self, cmd: ImportarPlanimetriaCommand) -> PotreroDTO:
        puntos = puntos_desde_geojson(cmd.geojson)
        resultado = self._validador.construir_y_validar(puntos)

        geometria = Geometria(
            puntos=tuple(Coordenada(lat=lat, lng=lng) for lat, lng in puntos),
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
