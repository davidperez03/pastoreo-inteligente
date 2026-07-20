"""Mapeo NDVI → biomasa (kg MS/ha) — soporte para la corrección Kalman (§5, §6).

PLACEHOLDER A CALIBRAR (fase 6): el mapeo real depende de la especie, el sensor
y la región, y debería ajustarse contra cortes de biomasa medidos en campo. Por
ahora es un mapeo lineal calibrable sobre un rango razonable de NDVI para
praderas tropicales, suficiente para probar la fusión modelo+sensor.
"""

from __future__ import annotations

from srp.agronomia.domain.crecimiento import ParametrosEspecie

# Parámetros por defecto del mapeo lineal (placeholder, calibrar en fase 6):
# NDVI en [NDVI_MIN, NDVI_MAX] mapea linealmente a [BIOMASA_MIN, BIOMASA_MAX].
NDVI_MIN = 0.2
NDVI_MAX = 0.9
BIOMASA_MIN = 300.0  # kg MS/ha (suelo casi desnudo / rebrote)
BIOMASA_MAX = 4500.0  # kg MS/ha (pradera densa)


def biomasa_desde_ndvi(ndvi: float, especie: ParametrosEspecie) -> float:
    """Biomasa equivalente (kg MS/ha) a partir de un NDVI promedio.

    Interpolación lineal entre (NDVI_MIN, BIOMASA_MIN) y (NDVI_MAX, BIOMASA_MAX),
    recortada a ese rango de biomasa. `especie` se recibe para permitir
    calibración por especie en el futuro (fase 6); hoy no altera el resultado.
    """
    _ = especie  # reservado para calibración por especie (fase 6)
    ndvi_clamp = max(NDVI_MIN, min(NDVI_MAX, ndvi))
    fraccion = (ndvi_clamp - NDVI_MIN) / (NDVI_MAX - NDVI_MIN)
    return BIOMASA_MIN + fraccion * (BIOMASA_MAX - BIOMASA_MIN)
