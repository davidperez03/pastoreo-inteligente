"""Evapotranspiración de referencia (ET0) por Hargreaves y radiación
extraterrestre por FAO-56 — §4.2.

`hargreaves_et0` solo necesita temperaturas (gratis vía Open-Meteo), pero
requiere la radiación extraterrestre Ra. Open-Meteo no siempre la entrega, así
que `radiacion_extraterrestre` la calcula de forma determinista a partir de la
latitud y el día juliano (FAO-56, ecuaciones 21-24).
"""

from __future__ import annotations

import math

# Constante solar (FAO-56): 0.0820 MJ/m²/min
_GSC = 0.0820


def radiacion_extraterrestre(latitud_grados: float, dia_juliano: int) -> float:
    """Radiación extraterrestre Ra en MJ/m²/día (FAO-56, ec. 21-24).

    Ra = (24*60/π) * Gsc * dr * [ωs·sin φ·sin δ + cos φ·cos δ·sin ωs]

    donde (con J = día juliano, 1..365/366):
      dr = 1 + 0.033·cos(2π/365 · J)          (ec. 23, distancia relativa tierra-sol)
      δ  = 0.409·sin(2π/365 · J − 1.39)        (ec. 24, declinación solar, rad)
      ωs = arccos(−tan φ · tan δ)              (ec. 25, ángulo horario de puesta de sol)
      φ  = latitud en radianes                 (ec. 22)

    En latitudes altas y ciertas épocas el argumento de arccos puede salir de
    [-1, 1] (sol de medianoche / noche polar); se recorta para robustez.
    """
    phi = math.radians(latitud_grados)
    dr = 1.0 + 0.033 * math.cos(2.0 * math.pi / 365.0 * dia_juliano)
    delta = 0.409 * math.sin(2.0 * math.pi / 365.0 * dia_juliano - 1.39)

    arg_ws = -math.tan(phi) * math.tan(delta)
    arg_ws = max(-1.0, min(1.0, arg_ws))
    omega_s = math.acos(arg_ws)

    ra = (
        (24.0 * 60.0 / math.pi)
        * _GSC
        * dr
        * (
            omega_s * math.sin(phi) * math.sin(delta)
            + math.cos(phi) * math.cos(delta) * math.sin(omega_s)
        )
    )
    return max(0.0, ra)


def hargreaves_et0(
    temp_max: float,
    temp_min: float,
    temp_media: float,
    radiacion_extraterrestre_mj: float,
) -> float:
    """ET0 diaria (mm) por Hargreaves-Samani (FAO-56).

    ET0 = 0.0023 · Ra · (Tmedia + 17.8) · (Tmax − Tmin)^0.5

    Ra debe expresarse en mm/día equivalente; en la práctica FAO usa Ra en
    MJ/m²/día directamente en esta forma calibrada de Hargreaves. La diferencia
    Tmax − Tmin no puede ser negativa; se recorta a 0.
    """
    rango = max(0.0, temp_max - temp_min)
    return 0.0023 * radiacion_extraterrestre_mj * (temp_media + 17.8) * math.sqrt(rango)
