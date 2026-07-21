"""Import desde DXF (CAD) con reproyección MAGNA-SIRGAS → WGS84 (§3.4-3.5).

Los planos CAD colombianos suelen venir en MAGNA-SIRGAS Origen Nacional
(EPSG:9377, metros); el resto del sistema trabaja en WGS84 (EPSG:4326).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import ezdxf
from pyproj import Transformer

CRS_MAGNA_SIRGAS = "EPSG:9377"
CRS_WGS84 = "EPSG:4326"


def dxf_a_geojson(path_dxf: str | Path) -> dict:
    """Extrae las polilíneas cerradas (LWPOLYLINE/POLYLINE) de un DXF como
    FeatureCollection GeoJSON, en el CRS original del plano (sin reproyectar).

    Cada polilínea con >= 3 vértices se convierte en un polígono; el nombre de
    la capa CAD se conserva en properties.nombre.
    """
    doc = ezdxf.readfile(str(path_dxf))
    msp = doc.modelspace()
    features: list[dict] = []
    for entity in msp.query("LWPOLYLINE POLYLINE"):
        if entity.dxftype() == "LWPOLYLINE":
            puntos = [(float(p[0]), float(p[1])) for p in entity.get_points()]
        else:  # POLYLINE clásica: vértices como entidades hijas
            puntos = [
                (float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices
            ]
        if len(puntos) < 3:
            continue
        anillo = list(puntos)
        if anillo[0] != anillo[-1]:
            anillo.append(anillo[0])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [anillo]},
                "properties": {"nombre": entity.dxf.layer},
            }
        )
    return {"type": "FeatureCollection", "features": features}


@lru_cache(maxsize=8)
def _transformer(crs_origen: str, crs_destino: str) -> Transformer:
    return Transformer.from_crs(crs_origen, crs_destino, always_xy=True)


def reproyectar_geojson(
    fc: dict,
    crs_origen: str = CRS_MAGNA_SIRGAS,
    crs_destino: str = CRS_WGS84,
) -> dict:
    """Reproyecta una FeatureCollection de polígonos entre CRS.

    Por defecto MAGNA-SIRGAS Origen Nacional (EPSG:9377) → WGS84 (EPSG:4326).
    Devuelve una copia; no muta la colección de entrada. Las coordenadas de
    salida quedan en orden GeoJSON (lng, lat).
    """
    transformer = _transformer(crs_origen, crs_destino)
    features: list[dict] = []
    for feature in fc.get("features", []):
        geometria = feature["geometry"]
        anillos = [
            [tuple(transformer.transform(x, y)) for x, y, *_ in anillo]
            for anillo in geometria["coordinates"]
        ]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": geometria["type"], "coordinates": anillos},
                "properties": dict(feature.get("properties") or {}),
            }
        )
    return {"type": "FeatureCollection", "features": features}
