"""Tests del adaptador mínimo ShapelyGeometriaValidator (§3.3, §14):
área geodésica plausible, autointersección, deduplicación y coordenadas
fuera de rango."""

from __future__ import annotations

import pytest

from srp.gestion_potreros.infrastructure.adapters.shapely_geometria_validator import (
    GeometriaInvalida,
    ShapelyGeometriaValidator,
)

# Cuadrado en Casanare de lado 0.004 grados (~444 m) => ~19.6 ha
CUADRADO = [
    (5.337, -72.396),
    (5.341, -72.396),
    (5.341, -72.392),
    (5.337, -72.392),
]


@pytest.fixture
def validador() -> ShapelyGeometriaValidator:
    return ShapelyGeometriaValidator()


def test_area_cuadrado_casanare(validador):
    resultado = validador.construir_y_validar(CUADRADO)
    assert resultado["area_ha"] == pytest.approx(19.6, rel=0.02)
    assert resultado["n_puntos"] == 4
    assert resultado["advertencia"] is None
    assert resultado["geojson"]["type"] == "Polygon"


def test_anillo_cerrado_y_puntos_duplicados_se_normalizan(validador):
    entrada = [CUADRADO[0], CUADRADO[0], *CUADRADO[1:], CUADRADO[0]]
    resultado = validador.construir_y_validar(entrada)
    assert resultado["n_puntos"] == 4
    assert resultado["area_ha"] == pytest.approx(19.6, rel=0.02)


def test_menos_de_tres_puntos_distintos_falla(validador):
    with pytest.raises(GeometriaInvalida):
        validador.construir_y_validar([CUADRADO[0], CUADRADO[0], CUADRADO[1]])


def test_poligono_autointersectado_se_corrige_con_advertencia(validador):
    # Orden "en corbata" (bow-tie): autointersección clásica de captura GPS
    corbata = [CUADRADO[0], CUADRADO[1], CUADRADO[3], CUADRADO[2]]
    resultado = validador.construir_y_validar(corbata)
    assert resultado["advertencia"] is not None
    assert resultado["area_ha"] > 0


def test_lat_fuera_de_rango_wgs84_falla(validador):
    with pytest.raises(GeometriaInvalida):
        validador.construir_y_validar([(95.0, -72.396), (95.1, -72.396), (95.1, -72.392)])


def test_lat_lng_invertidas_genera_advertencia(validador):
    # (lat=-72.4, lng=5.3) es un punto válido en WGS84 pero fuera del área de
    # uso de MAGNA-SIRGAS: el error más común de usuario (§14) debe avisarse
    invertidas = [(lng, lat) for lat, lng in CUADRADO]
    resultado = validador.construir_y_validar(invertidas)
    assert resultado["advertencia"] is not None
    assert "invertidas" in resultado["advertencia"]


def test_area_implausible_genera_advertencia(validador):
    # Cuadrado de ~1.1 grados de lado => decenas de miles de ha
    gigante = [(5.0, -73.0), (6.1, -73.0), (6.1, -71.9), (5.0, -71.9)]
    resultado = validador.construir_y_validar(gigante)
    assert resultado["advertencia"] is not None
