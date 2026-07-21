"""Tests puros de la actualización bayesiana del factor de fatiga (§8).

No usan fixtures de base de datos: son lógica de dominio pura.
"""

from __future__ import annotations

import pytest

from srp.calibracion.domain.bayes import (
    FACTOR_MAX,
    FACTOR_MIN,
    actualizar_factor_fatiga_bayesiano,
)


def test_n_ciclos_cero_salta_al_error_relativo():
    # Sin historial el prior no pesa: el factor salta directo al error_relativo.
    # error_relativo = 90 / 100 = 0.9
    factor, n = actualizar_factor_fatiga_bayesiano(
        factor_actual=1.0, n_ciclos=0, biomasa_predicha=100.0, biomasa_medida=90.0
    )
    assert factor == pytest.approx(0.9)
    assert n == 1


def test_n_ciclos_cero_error_relativo_se_clampa():
    # error_relativo = 300 / 100 = 3.0 -> clamp a FACTOR_MAX.
    factor, n = actualizar_factor_fatiga_bayesiano(
        factor_actual=1.0, n_ciclos=0, biomasa_predicha=100.0, biomasa_medida=300.0
    )
    assert factor == pytest.approx(FACTOR_MAX)
    assert n == 1


def test_historial_alto_una_observacion_atipica_mueve_poco():
    # Con n_ciclos=10 el prior domina: una observación atípica (error 0.5)
    # apenas mueve el factor desde 1.0.
    # nuevo = (1.0*10 + 0.5) / 11 = 10.5/11 ≈ 0.9545
    factor, n = actualizar_factor_fatiga_bayesiano(
        factor_actual=1.0, n_ciclos=10, biomasa_predicha=100.0, biomasa_medida=50.0
    )
    assert factor == pytest.approx(10.5 / 11)
    assert abs(factor - 1.0) < 0.05  # se movió poco
    assert n == 11


def test_clamp_extremo_inferior():
    # error_relativo muy bajo con poco historial -> por debajo de FACTOR_MIN.
    # nuevo = (0.5*0 + 0.1)/1 = 0.1 -> clamp a FACTOR_MIN.
    factor, n = actualizar_factor_fatiga_bayesiano(
        factor_actual=0.5, n_ciclos=0, biomasa_predicha=100.0, biomasa_medida=10.0
    )
    assert factor == pytest.approx(FACTOR_MIN)
    assert n == 1


def test_clamp_extremo_superior():
    factor, n = actualizar_factor_fatiga_bayesiano(
        factor_actual=1.3, n_ciclos=0, biomasa_predicha=100.0, biomasa_medida=500.0
    )
    assert factor == pytest.approx(FACTOR_MAX)
    assert n == 1


def test_secuencia_converge_hacia_el_error_observado():
    # Observaciones repetidas con error_relativo = 0.8 hacen converger el factor
    # hacia 0.8 (§8: el sistema mejora su precisión ciclo a ciclo).
    factor, n = 1.0, 0
    for _ in range(50):
        factor, n = actualizar_factor_fatiga_bayesiano(
            factor_actual=factor,
            n_ciclos=n,
            biomasa_predicha=100.0,
            biomasa_medida=80.0,
        )
    assert n == 50
    assert factor == pytest.approx(0.8, abs=0.01)


def test_guard_biomasa_predicha_no_positiva_no_actualiza():
    entrada = (1.0, 5)
    assert (
        actualizar_factor_fatiga_bayesiano(
            factor_actual=1.0, n_ciclos=5, biomasa_predicha=0.0, biomasa_medida=80.0
        )
        == entrada
    )
    assert (
        actualizar_factor_fatiga_bayesiano(
            factor_actual=1.0, n_ciclos=5, biomasa_predicha=-10.0, biomasa_medida=80.0
        )
        == entrada
    )


def test_guard_biomasa_medida_no_positiva_no_actualiza():
    entrada = (1.0, 5)
    assert (
        actualizar_factor_fatiga_bayesiano(
            factor_actual=1.0, n_ciclos=5, biomasa_predicha=100.0, biomasa_medida=0.0
        )
        == entrada
    )
    assert (
        actualizar_factor_fatiga_bayesiano(
            factor_actual=1.0, n_ciclos=5, biomasa_predicha=100.0, biomasa_medida=-5.0
        )
        == entrada
    )
