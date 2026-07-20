"""Adaptador del puerto `GeometriaValidator` del shared kernel (§18.4).

Implementación concreta basada en shapely/pyproj; es lo que los casos de uso
de otros contextos (p. ej. ImportarPlanimetria en gestión de potreros) reciben
inyectado como puerto.
"""

from __future__ import annotations

from srp.planimetria.poligono import construir_poligono_validado
from srp.shared.ports import GeometriaValidator


class PlanimetriaGeometriaValidator(GeometriaValidator):
    """Valida y construye polígonos de potrero a partir de puntos (lat, lng) WGS84."""

    def construir_y_validar(self, puntos: list[tuple[float, float]]) -> dict:
        """Devuelve {"geojson", "area_ha", "n_puntos", "advertencia"} (§3.3)."""
        return construir_poligono_validado(puntos)
