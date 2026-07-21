"""Adaptador MÍNIMO del puerto `GeometriaValidator` del shared kernel.

Implementación provisional para esta unidad: shapely `make_valid` + área
geodésica aproximada vía reproyección a MAGNA-SIRGAS 2018 / Origen-Nacional
(EPSG:9377). En la etapa de integración será reemplazada por el adaptador del
paquete de planimetría (otra unidad) — por eso NO se importa nada de
`srp.planimetria` aquí.
"""

from __future__ import annotations

from pyproj import CRS, Transformer
from shapely.geometry import Polygon, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as transformar
from shapely.validation import make_valid

from srp.shared.ports import GeometriaValidator

# Umbrales de plausibilidad de área (§3.3): fuera de este rango casi siempre
# significa lat/lng invertidas o unidades erróneas, no un potrero real.
_AREA_MIN_HA = 0.01
_AREA_MAX_HA = 5000.0

_A_MAGNA_SIRGAS = Transformer.from_crs("EPSG:4326", "EPSG:9377", always_xy=True)

# Área de uso de EPSG:9377 (Colombia). Fuera de estos límites la proyección
# distorsiona el área y casi siempre indica lat/lng invertidas (§3.3).
_USO = CRS("EPSG:9377").area_of_use


class GeometriaInvalida(ValueError):
    """La entrada no permite construir un polígono utilizable."""


def _mayor_poligono(geom: BaseGeometry) -> Polygon:
    """`make_valid` puede devolver Multi*/GeometryCollection; se toma el
    polígono de mayor área (el resto son astillas de la autointersección)."""
    if isinstance(geom, Polygon):
        return geom
    candidatos = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    if not candidatos:
        raise GeometriaInvalida("La geometría corregida no contiene ningún polígono")
    return max(candidatos, key=lambda g: g.area)


class ShapelyGeometriaValidator(GeometriaValidator):
    def construir_y_validar(self, puntos: list[tuple[float, float]]) -> dict:
        """Construye un polígono desde puntos WGS84 (lat, lng).

        Devuelve {"geojson", "area_ha", "n_puntos", "advertencia"} según el
        contrato del puerto (shared kernel).
        """
        # Deduplicar puntos consecutivos y descartar el cierre explícito
        unicos: list[tuple[float, float]] = []
        for lat, lng in puntos:
            par = (float(lat), float(lng))
            if not unicos or par != unicos[-1]:
                unicos.append(par)
        if len(unicos) > 1 and unicos[0] == unicos[-1]:
            unicos.pop()
        if len(unicos) < 3:
            raise GeometriaInvalida(
                "Se requieren al menos 3 puntos distintos para un potrero"
            )
        for lat, lng in unicos:
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                raise GeometriaInvalida(
                    f"Coordenada fuera de rango WGS84: lat={lat}, lng={lng} "
                    "(¿lat/lng invertidas?)"
                )

        advertencias: list[str] = []
        if _USO is not None and any(
            not (_USO.south <= lat <= _USO.north and _USO.west <= lng <= _USO.east)
            for lat, lng in unicos
        ):
            advertencias.append(
                "Coordenadas fuera del área de uso de MAGNA-SIRGAS (Colombia): "
                "el área calculada no es confiable (¿lat/lng invertidas?)"
            )

        poligono = Polygon([(lng, lat) for lat, lng in unicos])
        if not poligono.is_valid:
            poligono = _mayor_poligono(make_valid(poligono))
            advertencias.append("Polígono autointersectado: corregido automáticamente")

        area_m2 = transformar(_A_MAGNA_SIRGAS.transform, poligono).area
        area_ha = area_m2 / 10_000
        if area_ha <= 0:
            raise GeometriaInvalida("El polígono resultante tiene área nula")
        if not (_AREA_MIN_HA <= area_ha <= _AREA_MAX_HA):
            advertencias.append(
                f"Área implausible para un potrero ({area_ha:.2f} ha): "
                "revisar coordenadas (¿lat/lng invertidas?)"
            )

        return {
            "geojson": mapping(poligono),
            "area_ha": area_ha,
            "n_puntos": len(unicos),
            "advertencia": "; ".join(advertencias) if advertencias else None,
        }
