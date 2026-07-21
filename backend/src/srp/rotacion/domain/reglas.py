"""Reglas y constantes puras del motor de rotación (§7).

Todas las funciones son puras (sin I/O) y operan sobre valores planos; el
motor greedy las compone. Los valores son puntos de partida razonables para
bovinos en trópico bajo (Llanos/Casanare) y se calibrarán con datos reales en
la fase de calibración bayesiana (§8).
"""

from __future__ import annotations

from datetime import date

# Consumo de materia seca por Unidad Animal (UA = 450 kg de peso vivo) por
# día: ~2.7 % del peso vivo, estándar para bovinos en pastoreo tropical.
CONSUMO_UA_KG_MS: float = 12.0

# Fracción de la biomasa en pie que realmente se aprovecha: no se pastorea a
# ras — dejar residuo (~50 %) protege el rebrote y la corona de la planta.
UTILIZACION: float = 0.5

# Un potrero solo es candidato si su biomasa aprovechable cubre al menos este
# número de días de consumo del lote (evita movimientos demasiado frecuentes).
MIN_DIAS_PERMANENCIA: int = 3

# Tope de ocupación continua: aunque quede biomasa, más de 7 días en el mismo
# potrero degrada la selectividad y favorece el sobrepastoreo de manchones.
MAX_DIAS_PERMANENCIA: int = 7

# Multiplicador de score para potreros con fuente de agua propia: mover el
# lote a un potrero con agua evita infraestructura móvil y estrés del ganado.
BONUS_FUENTE_AGUA: float = 1.1


def dias_de_descanso(fecha_ultima_salida: date | None, fecha: date) -> int | None:
    """Días transcurridos desde la última salida de ganado del potrero.

    Devuelve None si el potrero no registra salida (nunca pastoreado o sin
    historial): se interpreta como descanso cumplido.
    """
    if fecha_ultima_salida is None:
        return None
    return (fecha - fecha_ultima_salida).days


def descanso_cumplido(
    fecha_ultima_salida: date | None, fecha: date, dias_descanso_ideal: int
) -> bool:
    dias = dias_de_descanso(fecha_ultima_salida, fecha)
    return dias is None or dias >= dias_descanso_ideal


def biomasa_aprovechable(biomasa_kg_ms_ha: float | None, area_ha: float) -> float:
    """Biomasa total aprovechable del potrero en kg MS (aplica UTILIZACION).

    Un potrero sin estimación de biomasa (None) aporta 0: sin dato no se
    envía ganado — el contexto agronómico (Kalman + NDVI) es quien alimenta
    `biomasa_kg_ms_ha` en la proyección.
    """
    if biomasa_kg_ms_ha is None or biomasa_kg_ms_ha <= 0 or area_ha <= 0:
        return 0.0
    return biomasa_kg_ms_ha * area_ha * UTILIZACION


def consumo_diario_lote(ua_equivalente: float) -> float:
    """Consumo diario del lote en kg MS/día."""
    return ua_equivalente * CONSUMO_UA_KG_MS


def score_potrero(
    biomasa_aprovechable_kg: float, factor_fatiga: float, fuente_agua: bool
) -> float:
    """Score greedy de un potrero candidato: biomasa aprovechable ponderada
    por el factor de fatiga (§8), con bonus si tiene fuente de agua."""
    bonus = BONUS_FUENTE_AGUA if fuente_agua else 1.0
    return biomasa_aprovechable_kg * factor_fatiga * bonus
