"""Actualización bayesiana del factor de fatiga por potrero (§8).

Cada potrero tiene comportamiento propio (microclima, sombra, suelo). El factor
de fatiga se aprende con cada ciclo real mediante una inferencia bayesiana
simple: el factor vigente actúa como media del prior con peso `n_ciclos`, y
cada nueva observación (una salida real de lote) aporta con peso 1.

Módulo puro: sin fastapi ni asyncpg (§18).
"""

from __future__ import annotations

# Rango físicamente plausible del factor de fatiga. Coincide con el CHECK de la
# columna potreros.factor_fatiga (0.5–1.3) para que el dominio nunca produzca
# un valor que la base rechazaría.
FACTOR_MIN = 0.5
FACTOR_MAX = 1.3


def _clamp(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))


def actualizar_factor_fatiga_bayesiano(
    factor_actual: float,
    n_ciclos: int,
    biomasa_predicha: float,
    biomasa_medida: float,
) -> tuple[float, int]:
    """Devuelve `(nuevo_factor, n_ciclos + 1)` tras una observación real.

    error_relativo = biomasa_medida / biomasa_predicha
    nuevo = (factor_actual * n_ciclos + error_relativo * 1) / (n_ciclos + 1)
    nuevo se clampa a [FACTOR_MIN, FACTOR_MAX].

    Con `n_ciclos = 0` el prior no tiene peso y el factor salta directo al
    error_relativo (clampeado). Con `n_ciclos` alto el prior domina y una
    observación atípica mueve poco el factor (§8: más historial = predicción
    más confiable).

    Guard: si `biomasa_predicha <= 0` o `biomasa_medida <= 0` NO se actualiza y
    se devuelve la entrada intacta `(factor_actual, n_ciclos)`. Motivos:
    - `biomasa_predicha <= 0` haría una división por cero o un error_relativo
      con signo/magnitud sin sentido físico (la biomasa es no negativa).
    - `biomasa_medida <= 0` implica una medición inválida o ausente; incorporar
      un error_relativo de 0 (o negativo) contaminaría el aprendizaje con un
      dato que no representa un ciclo real observable.
    En ambos casos preferimos no aprender nada antes que aprender basura: el
    contador `n_ciclos` tampoco avanza, porque no hubo observación válida.
    """
    if biomasa_predicha <= 0 or biomasa_medida <= 0:
        return factor_actual, n_ciclos

    error_relativo = biomasa_medida / biomasa_predicha
    nuevo_factor = (factor_actual * n_ciclos + error_relativo) / (n_ciclos + 1)
    return _clamp(nuevo_factor, FACTOR_MIN, FACTOR_MAX), n_ciclos + 1
