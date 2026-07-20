"""Tiempo térmico: grados-día de crecimiento (GDD) — §4.1.

El pasto acumula desarrollo en función de la temperatura por encima de un
umbral (`temp_base`), no del calendario. Para pastos C4 tropicales la base
ronda los 10 °C.
"""

from __future__ import annotations

from collections.abc import Iterable


def grados_dia(temp_media: float, temp_base: float) -> float:
    """Grados-día de un solo día.

    Es la contribución térmica del día: nula si la temperatura media queda por
    debajo del umbral en que el pasto crece.
    """
    return max(0.0, temp_media - temp_base)


def grados_dia_acumulados(
    temperaturas_medias: Iterable[float], temp_base: float
) -> float:
    """Acumulado de grados-día sobre una serie de temperaturas medias diarias."""
    return sum(grados_dia(t, temp_base) for t in temperaturas_medias)
