"""Contexto de planimetría (§3, §18): librería pura de levantamiento de potreros.

Todo converge a listas de (lat, lng) en WGS84 y de ahí a polígonos validados.
Sin FastAPI, sin base de datos, sin imports de otros contextos: solo
`srp.shared`, stdlib y librerías geoespaciales de terceros.
"""

from srp.planimetria.formatos import FormatoEntrada, normalizar_entrada
from srp.planimetria.poligono import (
    calcular_area_geodesica,
    construir_poligono_validado,
    validar_sin_traslape,
)
from srp.planimetria.validator import PlanimetriaGeometriaValidator

__all__ = [
    "FormatoEntrada",
    "PlanimetriaGeometriaValidator",
    "calcular_area_geodesica",
    "construir_poligono_validado",
    "normalizar_entrada",
    "validar_sin_traslape",
]
