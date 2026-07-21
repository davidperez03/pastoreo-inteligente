"""Tests de ET0 (Hargreaves) y radiación extraterrestre (FAO-56) (§4.2)."""

from __future__ import annotations

import math

from srp.agronomia.domain.et0 import hargreaves_et0, radiacion_extraterrestre


def test_hargreaves_contra_valor_calculado_a_mano() -> None:
    # Cálculo a mano de ET0 = 0.0023 * Ra * (Tmedia + 17.8) * sqrt(Tmax - Tmin)
    # con Tmax=30, Tmin=20, Tmedia=25, Ra=35 MJ/m²/día:
    #   0.0023 * 35 * (25 + 17.8) * sqrt(10)
    # = 0.0805 * 42.8 * 3.16227766...
    # = 3.4454 * 3.16227766...
    # = 10.8953 mm/día
    esperado = 0.0023 * 35 * (25 + 17.8) * math.sqrt(10)
    obtenido = hargreaves_et0(
        temp_max=30, temp_min=20, temp_media=25, radiacion_extraterrestre_mj=35
    )
    assert math.isclose(obtenido, esperado, rel_tol=1e-9)
    assert math.isclose(obtenido, 10.8953, abs_tol=1e-3)


def test_hargreaves_rango_negativo_se_recorta() -> None:
    # Tmax < Tmin no debe producir sqrt de negativo (NaN); se recorta a 0.
    et0 = hargreaves_et0(
        temp_max=18, temp_min=20, temp_media=19, radiacion_extraterrestre_mj=35
    )
    assert et0 == 0.0


def test_radiacion_extraterrestre_lat5_valor_fao() -> None:
    # FAO-56, Annex 2, Tabla 2.6: Ra para latitud 5°N a mediados de julio
    # (día juliano ~196) ≈ 35.5 MJ/m²/día. Tolerancia 5%.
    ra = radiacion_extraterrestre(latitud_grados=5.0, dia_juliano=196)
    assert math.isclose(ra, 35.5, rel_tol=0.05)


def test_radiacion_extraterrestre_valores_fisicos() -> None:
    # En el trópico Ra ronda 34-38 MJ/m²/día todo el año; nunca negativa.
    for dia in range(1, 366, 30):
        ra = radiacion_extraterrestre(latitud_grados=5.0, dia_juliano=dia)
        assert 30.0 < ra < 40.0
