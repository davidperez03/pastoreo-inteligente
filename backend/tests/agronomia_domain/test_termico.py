"""Tests de tiempo térmico (§4.1)."""

from __future__ import annotations

from srp.agronomia.domain.termico import grados_dia, grados_dia_acumulados


def test_gdd_temp_bajo_base_es_cero() -> None:
    # Temperatura media por debajo del umbral: sin desarrollo térmico.
    assert grados_dia(temp_media=8.0, temp_base=10.0) == 0.0
    assert grados_dia(temp_media=10.0, temp_base=10.0) == 0.0


def test_gdd_temp_sobre_base() -> None:
    assert grados_dia(temp_media=25.0, temp_base=10.0) == 15.0


def test_gdd_acumulado_ignora_dias_frios() -> None:
    # Solo los días con t > base aportan: 15 + 0 + 5 = 20.
    temps = [25.0, 8.0, 15.0]
    assert grados_dia_acumulados(temps, temp_base=10.0) == 20.0
