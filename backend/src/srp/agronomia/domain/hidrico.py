"""Balance hídrico de suelo (bucket model) — §4.2.

El suelo se modela como un depósito con capacidad de campo: cada día entra
precipitación y sale evapotranspiración del cultivo. La memoria del agua
retenida día a día es lo que permite predecir bien la transición
lluvia→sequía típica de Casanare (el pasto no colapsa el primer día seco).
"""

from __future__ import annotations

KC_PASTO_DEFECTO = 0.9  # coeficiente de cultivo del pasto (~0.85-1.0)


def balance_hidrico_diario(
    suelo_actual_mm: float,
    precipitacion_mm: float,
    capacidad_campo_mm: float,
    et0_mm: float,
    kc_pasto: float = KC_PASTO_DEFECTO,
) -> float:
    """Agua en el suelo al final del día, en mm.

    entrada = precipitación; salida = ET0 * Kc. El resultado se recorta al
    intervalo [0, capacidad_campo]: el suelo no retiene más de su capacidad de
    campo (el excedente escurre/percola) ni baja de cero.
    """
    entrada = precipitacion_mm
    salida = et0_mm * kc_pasto
    suelo_nuevo = suelo_actual_mm + entrada - salida
    suelo_nuevo = min(capacidad_campo_mm, suelo_nuevo)
    return max(0.0, suelo_nuevo)


def fraccion_agua_disponible(suelo_mm: float, capacidad_mm: float) -> float:
    """Fracción de agua disponible en [0, 1] (suelo / capacidad de campo).

    Es el factor hídrico que modula el crecimiento (§4.3). Con capacidad no
    positiva no hay agua disponible: se devuelve 0.
    """
    if capacidad_mm <= 0:
        return 0.0
    return max(0.0, min(1.0, suelo_mm / capacidad_mm))
