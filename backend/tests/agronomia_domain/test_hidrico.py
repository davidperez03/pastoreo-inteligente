"""Tests del balance hídrico de suelo (§4.2)."""

from __future__ import annotations

from srp.agronomia.domain.hidrico import (
    balance_hidrico_diario,
    fraccion_agua_disponible,
)


def test_bucket_no_supera_capacidad() -> None:
    # Lluvia enorme sobre suelo ya casi lleno: no pasa de la capacidad de campo.
    suelo = balance_hidrico_diario(
        suelo_actual_mm=90.0,
        precipitacion_mm=500.0,
        capacidad_campo_mm=100.0,
        et0_mm=4.0,
    )
    assert suelo == 100.0


def test_bucket_no_baja_de_cero() -> None:
    # Sin lluvia y con demanda evaporativa alta sobre suelo casi vacío: clamp a 0.
    suelo = balance_hidrico_diario(
        suelo_actual_mm=2.0,
        precipitacion_mm=0.0,
        capacidad_campo_mm=100.0,
        et0_mm=10.0,
    )
    assert suelo == 0.0


def test_bucket_balance_intermedio() -> None:
    # 50 + 20 - (5 * 0.9) = 65.5
    suelo = balance_hidrico_diario(
        suelo_actual_mm=50.0,
        precipitacion_mm=20.0,
        capacidad_campo_mm=100.0,
        et0_mm=5.0,
    )
    assert suelo == 65.5


def test_fraccion_agua_disponible_en_rango() -> None:
    assert fraccion_agua_disponible(50.0, 100.0) == 0.5
    assert fraccion_agua_disponible(200.0, 100.0) == 1.0  # clamp superior
    assert fraccion_agua_disponible(-5.0, 100.0) == 0.0  # clamp inferior
    assert fraccion_agua_disponible(50.0, 0.0) == 0.0  # capacidad no positiva
