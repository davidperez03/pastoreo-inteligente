"""Parsers de coordenadas: lista manual (decimal y GMS), CSV y GPX/KML (§3.2-3.3).

Contrato: todas las funciones devuelven `list[tuple[float, float]]` como
(lat, lng) en WGS84.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

# 5°20'16.1"N — grados, minutos, segundos y hemisferio (O = Oeste, sinónimo de W)
_GMS_RE = re.compile(
    r"""(?P<grados>\d{1,3})\s*[°º]\s*
        (?P<minutos>\d{1,2})\s*['′]\s*
        (?P<segundos>\d{1,2}(?:\.\d+)?)\s*["″]\s*
        (?P<hemisferio>[NSEWO])""",
    re.VERBOSE | re.IGNORECASE,
)

_DECIMAL_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")

_NOMBRES_LAT = {"lat", "latitud", "latitude", "y"}
_NOMBRES_LNG = {"lng", "lon", "long", "longitud", "longitude", "x"}


def _gms_a_decimal(grados: str, minutos: str, segundos: str, hemisferio: str) -> float:
    valor = float(grados) + float(minutos) / 60.0 + float(segundos) / 3600.0
    if hemisferio.upper() in ("S", "W", "O"):
        valor = -valor
    return valor


def _parsear_linea_gms(linea: str) -> tuple[float, float]:
    """Convierte una línea GMS ('5°20'16.1"N 72°23'45.2"W') a (lat, lng)."""
    lat: float | None = None
    lng: float | None = None
    for m in _GMS_RE.finditer(linea):
        valor = _gms_a_decimal(
            m.group("grados"), m.group("minutos"), m.group("segundos"), m.group("hemisferio")
        )
        if m.group("hemisferio").upper() in ("N", "S"):
            lat = valor
        else:
            lng = valor
    if lat is None or lng is None:
        raise ValueError(f"Línea GMS incompleta (falta latitud o longitud): {linea!r}")
    return (lat, lng)


def _parsear_linea_decimal(linea: str) -> tuple[float, float]:
    numeros = _DECIMAL_RE.findall(linea)
    if len(numeros) < 2:
        raise ValueError(f"Línea sin dos coordenadas decimales: {linea!r}")
    return (float(numeros[0]), float(numeros[1]))


def parsear_lista_manual(texto: str) -> list[tuple[float, float]]:
    """Parsea una lista de coordenadas tecleadas por el usuario, una por línea.

    Acepta formato decimal ("5.3378, -72.3959") y GMS
    ('5°20'16.1"N 72°23'45.2"W'), incluso mezclados. Devuelve (lat, lng).
    """
    puntos: list[tuple[float, float]] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if _GMS_RE.search(linea):
            puntos.append(_parsear_linea_gms(linea))
        else:
            puntos.append(_parsear_linea_decimal(linea))
    return puntos


def parsear_csv_coordenadas(archivo_o_texto: str | Path) -> list[tuple[float, float]]:
    """Parsea un CSV con columnas de latitud y longitud.

    Reconoce cabeceras (lat/latitud/latitude, lng/lon/longitud/longitude, en
    cualquier orden); sin cabecera asume columnas (lat, lng). Acepta una ruta
    a archivo o el contenido CSV como texto.
    """
    contenido = _leer_texto(archivo_o_texto)
    filas = [f for f in csv.reader(io.StringIO(contenido)) if f and any(c.strip() for c in f)]
    if not filas:
        return []

    idx_lat, idx_lng = 0, 1
    cabecera = [c.strip().lower() for c in filas[0]]
    if any(c in _NOMBRES_LAT or c in _NOMBRES_LNG for c in cabecera):
        try:
            idx_lat = next(i for i, c in enumerate(cabecera) if c in _NOMBRES_LAT)
            idx_lng = next(i for i, c in enumerate(cabecera) if c in _NOMBRES_LNG)
        except StopIteration as exc:
            raise ValueError(f"Cabecera CSV sin columnas lat/lng reconocibles: {cabecera}") from exc
        filas = filas[1:]

    puntos: list[tuple[float, float]] = []
    for fila in filas:
        try:
            puntos.append((float(fila[idx_lat]), float(fila[idx_lng])))
        except (ValueError, IndexError) as exc:
            raise ValueError(f"Fila CSV inválida: {fila}") from exc
    return puntos


def leer_gpx_kml(archivo: str | Path) -> list[tuple[float, float]]:
    """Lee la primera geometría de un GPX o KML con geopandas y devuelve (lat, lng).

    GPX: intenta las capas 'tracks' y 'routes' (un lindero caminado es un track).
    KML: lee el primer Placemark (polígono o línea). Descarta la altitud (z).
    """
    import geopandas as gpd  # import perezoso: pesado, solo se paga si se usa

    ruta = str(archivo)
    geometria = None
    if ruta.lower().endswith(".gpx"):
        for capa in ("tracks", "routes"):
            try:
                gdf = gpd.read_file(ruta, layer=capa)
            except Exception:  # noqa: BLE001 — capa ausente o vacía según el driver
                continue
            serie = gdf.geometry.dropna()
            if len(serie) and not serie.iloc[0].is_empty:
                geometria = serie.iloc[0]
                break
    else:
        gdf = gpd.read_file(ruta)
        serie = gdf.geometry.dropna()
        if len(serie):
            geometria = serie.iloc[0]

    if geometria is None or geometria.is_empty:
        raise ValueError(f"El archivo no contiene geometrías legibles: {ruta}")
    return coords_a_lat_lng(_extraer_coords(geometria))


def _extraer_coords(geometria) -> list[tuple[float, ...]]:
    """Extrae el anillo/línea principal de una geometría shapely como (x, y[, z])."""
    tipo = geometria.geom_type
    if tipo == "Polygon":
        return list(geometria.exterior.coords)
    if tipo in ("MultiPolygon", "MultiLineString", "GeometryCollection"):
        return _extraer_coords(max(geometria.geoms, key=lambda g: g.length))
    if tipo in ("LineString", "LinearRing"):
        return list(geometria.coords)
    raise ValueError(f"Tipo de geometría no soportado para un lindero: {tipo}")


def coords_a_lat_lng(coords: list[tuple[float, ...]]) -> list[tuple[float, float]]:
    """Convierte coordenadas GIS (x=lng, y=lat[, z]) al contrato (lat, lng)."""
    return [(c[1], c[0]) for c in coords]


def _leer_texto(archivo_o_texto: str | Path) -> str:
    if isinstance(archivo_o_texto, Path):
        return archivo_o_texto.read_text(encoding="utf-8")
    # Un string corto sin saltos de línea que apunta a un archivo existente es una ruta
    if "\n" not in archivo_o_texto and len(archivo_o_texto) < 4096:
        posible = Path(archivo_o_texto)
        try:
            if posible.is_file():
                return posible.read_text(encoding="utf-8")
        except OSError:
            pass
    return archivo_o_texto
