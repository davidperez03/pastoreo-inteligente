"""Commands y DTOs de la capa de aplicación (§18.3).

Los commands llegan con la entrada YA normalizada: lista de puntos (lat, lng)
o GeoJSON. El parseo de archivos (GPX/DXF/KML) es responsabilidad del paquete
de planimetría de otra unidad y se integra después — aquí no se leen archivos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from srp.shared.types import FincaId, PotreroId


@dataclass(frozen=True)
class RegistrarPotreroManualCommand:
    finca_id: FincaId
    nombre: str
    puntos: tuple[tuple[float, float], ...]  # (lat, lng) WGS84, ya normalizados
    especie_pasto_id: uuid.UUID
    metodo_levantamiento: str
    tipo_suelo: str | None = None
    fuente_agua: bool = False
    accuracy_m: float | None = None


@dataclass(frozen=True)
class ImportarPlanimetriaCommand:
    """El GeoJSON viene ya extraído/reproyectado a WGS84 por el paquete de
    planimetría (otra unidad). Acepta geometría Polygon o Feature/Polygon."""

    finca_id: FincaId
    nombre: str
    geojson: dict
    especie_pasto_id: uuid.UUID
    metodo_levantamiento: str
    tipo_suelo: str | None = None
    fuente_agua: bool = False
    accuracy_m: float | None = None


@dataclass(frozen=True)
class PotreroDTO:
    """Proyección plana del agregado para los adaptadores de entrada."""

    id: PotreroId
    finca_id: FincaId
    nombre: str
    area_ha: float
    estado: str
    especie_pasto_id: uuid.UUID
    tipo_suelo: str | None
    fuente_agua: bool
    factor_fatiga: float
    metodo_levantamiento: str
    accuracy_m: float | None
    fecha_ultima_salida: date | None
    biomasa_actual_kg_ms_ha: float | None
    geojson: dict
    advertencia: str | None = None


def potrero_a_dto(potrero, advertencia: str | None = None) -> PotreroDTO:  # noqa: ANN001
    """Mapea el agregado a su proyección plana. Recibe `Potrero` (tipado laxo
    para evitar import circular dominio<->dto)."""
    return PotreroDTO(
        id=potrero.id,
        finca_id=potrero.finca_id,
        nombre=potrero.nombre,
        area_ha=potrero.area_ha,
        estado=potrero.estado.value,
        especie_pasto_id=potrero.especie_pasto_id,
        tipo_suelo=potrero.tipo_suelo,
        fuente_agua=potrero.fuente_agua,
        factor_fatiga=potrero.factor_fatiga.valor,
        metodo_levantamiento=potrero.geometria.metodo_levantamiento,
        accuracy_m=potrero.geometria.accuracy_m,
        fecha_ultima_salida=potrero.fecha_ultima_salida,
        biomasa_actual_kg_ms_ha=potrero.biomasa_actual_kg_ms_ha,
        geojson=potrero.geojson,
        advertencia=advertencia,
    )
