"""Construcción y validación de polígonos de potrero (§3.3).

Reglas:
- mínimo 3 puntos distintos, cierre automático del anillo;
- autointersecciones corregidas con `make_valid` + advertencia;
- área geodésica calculada proyectando a MAGNA-SIRGAS (EPSG:9377), precisa
  para Colombia y sin el error de la proyección plana cerca del Ecuador;
- umbral de plausibilidad 0.05-5000 ha: atrapa el error más común del usuario
  final (invertir lat/lng), que produce un polígono "válido" pero absurdo;
- el traslape entre potreros se advierte, no se bloquea (potreros contiguos
  legítimos pueden compartir cerca).
"""

from __future__ import annotations

import math
from functools import lru_cache

from pyproj import CRS, Transformer
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.validation import explain_validity, make_valid

AREA_MINIMA_PLAUSIBLE_HA = 0.05
AREA_MAXIMA_PLAUSIBLE_HA = 5000.0
M2_POR_HECTAREA = 10_000.0


@lru_cache(maxsize=1)
def _proyeccion_a_magna_sirgas():
    """WGS84 (EPSG:4326) → MAGNA-SIRGAS Origen Nacional (EPSG:9377, metros)."""
    return Transformer.from_crs("EPSG:4326", "EPSG:9377", always_xy=True).transform


@lru_cache(maxsize=1)
def _area_de_uso_epsg9377() -> tuple[float, float, float, float]:
    """(west, south, east, north) del área de validez de EPSG:9377 (Colombia)."""
    a = CRS("EPSG:9377").area_of_use
    return (a.west, a.south, a.east, a.north)


def _fuera_de_colombia(poligono: BaseGeometry) -> bool:
    """True si el polígono cae fuera del área de validez de MAGNA-SIRGAS.

    Fuera de ella la proyección devuelve números finitos pero sin sentido, con
    lo que el área "plausible" es un espejismo. Es el síntoma típico de teclear
    lat/lng invertidas: (5.34, -72.4) se convierte en un punto en el océano
    Antártico (lng 5.34, lat -72.4)."""
    west, south, east, north = _area_de_uso_epsg9377()
    min_lng, min_lat, max_lng, max_lat = poligono.bounds
    return min_lng < west or max_lng > east or min_lat < south or max_lat > north


def calcular_area_geodesica(poligono: BaseGeometry) -> float:
    """Área real en m² de una geometría en WGS84 (lng, lat), proyectada a EPSG:9377."""
    return transform(_proyeccion_a_magna_sirgas(), poligono).area


def construir_poligono_validado(puntos: list[tuple[float, float]]) -> dict:
    """Construye un polígono validado a partir de puntos (lat, lng) WGS84.

    Devuelve {"geojson", "area_ha", "n_puntos", "advertencia"}. Lanza
    ValueError con menos de 3 puntos distintos. No muta la lista de entrada.
    """
    puntos = list(puntos)
    if puntos and puntos[0] == puntos[-1]:
        puntos.pop()  # anillo ya cerrado: el cierre no cuenta como punto propio
    if len(puntos) < 3:
        raise ValueError("Se necesitan mínimo 3 puntos para un polígono")
    puntos.append(puntos[0])  # cierre automático

    # GeoJSON y shapely usan (lng, lat); el contrato de entrada es (lat, lng)
    poligono: BaseGeometry = Polygon([(lng, lat) for lat, lng in puntos])

    advertencia: str | None = None
    if not poligono.is_valid:
        razon = explain_validity(poligono)
        poligono = make_valid(poligono)
        advertencia = f"Polígono corregido automáticamente: {razon}"

    area_ha = calcular_area_geodesica(poligono) / M2_POR_HECTAREA
    # Plausibilidad: área fuera de rango, área no finita (proyección degenerada)
    # o polígono fuera del área de validez de EPSG:9377 — los tres son el
    # síntoma típico de lat/lng invertidas u otro error de digitación.
    if (
        not math.isfinite(area_ha)
        or area_ha < AREA_MINIMA_PLAUSIBLE_HA
        or area_ha > AREA_MAXIMA_PLAUSIBLE_HA
        or _fuera_de_colombia(poligono)
    ):
        aviso_area = (
            f"Área calculada ({area_ha:.2f} ha) fuera de rango plausible "
            f"({AREA_MINIMA_PLAUSIBLE_HA}-{AREA_MAXIMA_PLAUSIBLE_HA} ha) o polígono "
            "fuera del área de validez de MAGNA-SIRGAS (Colombia); ¿lat/lng invertidas?"
        )
        advertencia = f"{advertencia} {aviso_area}" if advertencia else aviso_area

    return {
        "geojson": poligono.__geo_interface__,
        "area_ha": area_ha,
        "n_puntos": len(puntos),
        "advertencia": advertencia,
    }


def validar_sin_traslape(
    nuevo: BaseGeometry,
    existentes: list[tuple[str, BaseGeometry]],
) -> list[str]:
    """Devuelve los nombres de potreros existentes que se traslapan con `nuevo`.

    Función pura sobre geometrías shapely (el adaptador de persistencia decide
    de dónde salen las geometrías existentes). Un traslape casi siempre es error
    de digitalización (deriva de GPS, punto mal tecleado): se advierte, no se
    bloquea. Compartir solo el borde (potreros contiguos con cerca común) no
    cuenta como traslape: se exige intersección con área positiva.
    """
    traslapes: list[str] = []
    for nombre, geometria in existentes:
        if nuevo.intersects(geometria) and nuevo.intersection(geometria).area > 0:
            traslapes.append(nombre)
    return traslapes
