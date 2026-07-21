"""Tests del filtro de Kalman de biomasa (§5)."""

from __future__ import annotations

from srp.agronomia.domain.kalman import KalmanBiomasa


def test_converge_hacia_observaciones_repetidas_y_p_decrece() -> None:
    kf = KalmanBiomasa(biomasa_inicial=1000.0, varianza_inicial=100.0)
    observacion = 2500.0
    p_tras_primera = None
    for _ in range(50):
        # Ciclo realista: el modelo no aporta crecimiento (predecir 0) y el NDVI
        # observa siempre lo mismo; el filtro debe converger a la observación.
        kf.predecir(0.0)
        p_antes = kf.P
        kf.actualizar(observacion, calidad_lectura=1.0)
        assert kf.P < p_antes  # cada corrección reduce la incertidumbre
        if p_tras_primera is None:
            p_tras_primera = kf.P
    # La incertidumbre en régimen es mucho menor que tras la primera corrección.
    assert kf.P < p_tras_primera
    # Tras muchas observaciones consistentes, el estado converge a la observación.
    assert abs(kf.x - observacion) < 1.0


def test_calidad_baja_corrige_minimamente() -> None:
    innovacion_objetivo = 3000.0

    kf_alta = KalmanBiomasa(biomasa_inicial=1000.0, varianza_inicial=100.0)
    kf_alta.actualizar(innovacion_objetivo, calidad_lectura=1.0)
    movimiento_alta = kf_alta.x - 1000.0

    kf_baja = KalmanBiomasa(biomasa_inicial=1000.0, varianza_inicial=100.0)
    kf_baja.actualizar(innovacion_objetivo, calidad_lectura=0.0)  # nubosidad total
    movimiento_baja = kf_baja.x - 1000.0

    # Una lectura sin calidad apenas mueve el estado frente a una de calidad plena.
    assert movimiento_baja > 0.0
    assert movimiento_baja < movimiento_alta * 0.4


def test_predecir_aumenta_estado_e_incertidumbre() -> None:
    kf = KalmanBiomasa(biomasa_inicial=500.0, varianza_inicial=50.0)
    kf.predecir(crecimiento_estimado_dia=40.0)
    assert kf.x == 540.0
    assert kf.P == 50.0 + KalmanBiomasa.Q
