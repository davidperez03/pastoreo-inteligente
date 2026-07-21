"""Pipeline agnóstico a la fuente (§3.2): todo converge a (lat, lng) WGS84."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from srp.planimetria.dxf import dxf_a_geojson, reproyectar_geojson
from srp.planimetria.parsers import (
    coords_a_lat_lng,
    leer_gpx_kml,
    parsear_csv_coordenadas,
    parsear_lista_manual,
)


class FormatoEntrada(Enum):
    LISTA_MANUAL = "lista_manual"
    GPX = "gpx"
    KML = "kml"
    CSV = "csv"
    DXF = "dxf"


def normalizar_entrada(
    archivo_o_texto: str | Path, formato: FormatoEntrada
) -> list[tuple[float, float]]:
    """Todo converge a una lista de (lat, lng) en WGS84.

    - LISTA_MANUAL: texto tecleado (decimal o GMS).
    - CSV: ruta a archivo o contenido CSV.
    - GPX / KML: ruta a archivo (ya vienen en WGS84).
    - DXF: ruta a archivo en MAGNA-SIRGAS EPSG:9377; se reproyecta a WGS84.
    """
    match formato:
        case FormatoEntrada.LISTA_MANUAL:
            return parsear_lista_manual(str(archivo_o_texto))
        case FormatoEntrada.GPX | FormatoEntrada.KML:
            return leer_gpx_kml(archivo_o_texto)
        case FormatoEntrada.CSV:
            return parsear_csv_coordenadas(archivo_o_texto)
        case FormatoEntrada.DXF:
            fc = dxf_a_geojson(archivo_o_texto)
            fc_wgs84 = reproyectar_geojson(fc)  # MAGNA-SIRGAS -> WGS84
            if not fc_wgs84["features"]:
                raise ValueError(f"El DXF no contiene polilíneas cerradas: {archivo_o_texto}")
            anillo = fc_wgs84["features"][0]["geometry"]["coordinates"][0]
            return coords_a_lat_lng(anillo)
    raise ValueError(f"Formato de entrada no soportado: {formato}")  # pragma: no cover
