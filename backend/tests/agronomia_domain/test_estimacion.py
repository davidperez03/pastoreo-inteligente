"""Tests del agregado EstimacionBiomasa (§17.2): integración modelo + Kalman."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from itertools import pairwise

from srp.agronomia.domain.crecimiento import ParametrosEspecie
from srp.agronomia.domain.estimacion import EstadoSuelo, EstimacionBiomasa
from srp.agronomia.domain.events import BiomasaRecalculada
from srp.agronomia.domain.kalman import KalmanBiomasa
from srp.shared.types import LecturaNdvi, PotreroId, RegistroClima

ESPECIE = ParametrosEspecie(
    nombre="Brachiaria",
    temp_base=10.0,
    tasa_max_crecimiento=100.0,
    gdd_optimo_diario=15.0,
    dias_descanso_ideal=30,
    curva_k=0.5,
)
SUELO = EstadoSuelo(
    capacidad_campo_mm=100.0, tipo_suelo="franco", latitud_grados=5.0, factor_fatiga=1.0
)


def _estimacion(suelo_inicial: float = 50.0) -> EstimacionBiomasa:
    kf = KalmanBiomasa(biomasa_inicial=1000.0, varianza_inicial=100.0)
    return EstimacionBiomasa(
        PotreroId(uuid.uuid4()), kf, suelo_actual_mm=suelo_inicial
    )


def _clima(dia: date, precipitacion: float) -> RegistroClima:
    return RegistroClima(
        fecha=dia,
        temp_media=25.0,
        temp_max=30.0,
        temp_min=20.0,
        precipitacion_mm=precipitacion,
    )


def test_transicion_lluvia_sequia_decae_gradual_con_memoria_de_suelo() -> None:
    est = _estimacion()
    d0 = date(2026, 6, 1)

    # 10 días de lluvia: el suelo llega y se mantiene en capacidad de campo.
    prev = est.biomasa_kg_ms_ha
    for i in range(10):
        est.actualizar_con_clima(_clima(d0 + timedelta(days=i), 25.0), ESPECIE, SUELO)
        prev = est.biomasa_kg_ms_ha
    assert est.suelo_mm == SUELO.capacidad_campo_mm

    # 5 días secos: el crecimiento decae, pero de forma gradual (memoria del suelo),
    # no de golpe — el primer día seco aún crece cerca del máximo.
    crecimientos_secos = []
    for i in range(5):
        est.actualizar_con_clima(
            _clima(d0 + timedelta(days=10 + i), 0.0), ESPECIE, SUELO
        )
        crecimientos_secos.append(est.biomasa_kg_ms_ha - prev)
        prev = est.biomasa_kg_ms_ha

    # Primer día seco: todavía crece fuerte (no colapsa).
    assert crecimientos_secos[0] > 0.8 * ESPECIE.tasa_max_crecimiento
    # Decaimiento estrictamente monótono y suave (cada día > mitad del anterior).
    for anterior, siguiente in pairwise(crecimientos_secos):
        assert siguiente < anterior  # decae
        assert siguiente > 0.5 * anterior  # gradual, no de golpe
    # El quinto día seco aún crece: la memoria del suelo no se agotó de golpe.
    assert crecimientos_secos[-1] > 0.0


def test_actualizar_con_clima_emite_evento_modelo() -> None:
    est = _estimacion()
    est.actualizar_con_clima(_clima(date(2026, 6, 1), 20.0), ESPECIE, SUELO)
    eventos = est.eventos_pendientes()
    assert len(eventos) == 1
    evento = eventos[0]
    assert isinstance(evento, BiomasaRecalculada)
    assert evento.fuente == "modelo"
    assert evento.biomasa_kg_ms_ha == est.biomasa_kg_ms_ha


def test_corregir_con_ndvi_emite_evento_kalman_y_mueve_estado() -> None:
    est = _estimacion()
    x_previa = est.biomasa_kg_ms_ha
    lectura = LecturaNdvi(fecha=date(2026, 6, 1), ndvi_promedio=0.8, calidad=1.0)
    est.corregir_con_ndvi(lectura, ESPECIE)
    assert est.biomasa_kg_ms_ha != x_previa
    eventos = est.eventos_pendientes()
    assert len(eventos) == 1
    assert eventos[0].fuente == "kalman"


def test_corregir_con_ndvi_ignora_lecturas_stale() -> None:
    est = _estimacion()
    x_previa = est.biomasa_kg_ms_ha
    lectura = LecturaNdvi(
        fecha=date(2026, 6, 1), ndvi_promedio=0.8, calidad=1.0, stale=True
    )
    est.corregir_con_ndvi(lectura, ESPECIE)
    # Lectura stale: ni mueve el estado ni emite evento.
    assert est.biomasa_kg_ms_ha == x_previa
    assert est.eventos_pendientes() == []
