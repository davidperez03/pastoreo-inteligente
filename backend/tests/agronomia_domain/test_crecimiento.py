"""Tests del crecimiento diario acoplado (§4.3)."""

from __future__ import annotations

from srp.agronomia.domain.crecimiento import (
    SUELO_FACTOR,
    ParametrosEspecie,
    crecimiento_diario_v2,
)

BRACHIARIA = ParametrosEspecie(
    nombre="Brachiaria",
    temp_base=10.0,
    tasa_max_crecimiento=100.0,
    gdd_optimo_diario=15.0,
    dias_descanso_ideal=30,
    curva_k=0.5,
)


def test_factor_fatiga_bajo_reduce_proporcionalmente() -> None:
    args = dict(gdd_hoy=15.0, fraccion_hidrica=1.0, especie=BRACHIARIA, tipo_suelo="franco")
    pleno = crecimiento_diario_v2(**args, factor_fatiga=1.0)
    fatigado = crecimiento_diario_v2(**args, factor_fatiga=0.5)
    # La fatiga entra como factor multiplicativo lineal.
    assert fatigado == pleno * 0.5


def test_suelo_factor_modula() -> None:
    args = dict(gdd_hoy=15.0, fraccion_hidrica=1.0, especie=BRACHIARIA, factor_fatiga=1.0)
    franco = crecimiento_diario_v2(**args, tipo_suelo="franco")
    arenoso = crecimiento_diario_v2(**args, tipo_suelo="arenoso")
    assert arenoso == franco * SUELO_FACTOR["arenoso"]


def test_tipo_suelo_none_es_neutro() -> None:
    args = dict(gdd_hoy=15.0, fraccion_hidrica=1.0, especie=BRACHIARIA, factor_fatiga=1.0)
    assert crecimiento_diario_v2(**args, tipo_suelo=None) == crecimiento_diario_v2(
        **args, tipo_suelo="franco"
    )


def test_factor_termico_satura_en_uno() -> None:
    # GDD muy por encima del óptimo no crece más que el potencial (con f=1 en todo).
    c = crecimiento_diario_v2(
        gdd_hoy=1000.0,
        fraccion_hidrica=1.0,
        especie=BRACHIARIA,
        tipo_suelo="franco",
        factor_fatiga=1.0,
    )
    assert c == BRACHIARIA.tasa_max_crecimiento


def test_sin_agua_no_crece() -> None:
    c = crecimiento_diario_v2(
        gdd_hoy=15.0,
        fraccion_hidrica=0.0,
        especie=BRACHIARIA,
        tipo_suelo="franco",
        factor_fatiga=1.0,
    )
    assert c == 0.0
