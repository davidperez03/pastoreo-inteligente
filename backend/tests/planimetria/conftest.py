"""Fixtures del contexto de planimetría: puro dominio, sin base de datos.

El potrero de referencia es un cuadrado en Casanare de lado 0.004°
(~443-445 m por lado a esa latitud), es decir ~19.6-19.7 ha.
"""

from __future__ import annotations

import pytest

# (lat, lng) WGS84 — esquinas del cuadrado, sin cerrar
CUADRADO_CASANARE: list[tuple[float, float]] = [
    (5.337, -72.396),
    (5.337, -72.392),
    (5.341, -72.392),
    (5.341, -72.396),
]

AREA_ESPERADA_HA = 19.6


@pytest.fixture
def cuadrado_casanare() -> list[tuple[float, float]]:
    return list(CUADRADO_CASANARE)
