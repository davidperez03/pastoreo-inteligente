"""Crecimiento diario acoplado de biomasa — §4.3.

El crecimiento potencial de la especie se modula por cuatro factores en [0, 1]:
térmico (GDD), hídrico (agua disponible), suelo (textura) y fatiga (memoria
del potrero). El acople multiplicativo hace que cualquier factor limitante
domine, como en la realidad agronómica.
"""

from __future__ import annotations

from dataclasses import dataclass

# Factor de crecimiento por textura de suelo. None -> franco (neutro).
SUELO_FACTOR: dict[str | None, float] = {
    "franco": 1.0,
    "arcilloso": 0.9,
    "arenoso": 0.8,
    None: 1.0,
}


@dataclass(frozen=True)
class ParametrosEspecie:
    """Parámetros agronómicos de una especie de pasto.

    - `temp_base`: umbral térmico bajo el cual no crece (°C).
    - `tasa_max_crecimiento`: crecimiento potencial diario (kg MS/ha/día).
    - `gdd_optimo_diario`: GDD que satura el factor térmico.
    - `dias_descanso_ideal`: descanso recomendado entre pastoreos.
    - `curva_k`: parámetro de forma de la curva de acumulación (calibrable).
    """

    nombre: str
    temp_base: float
    tasa_max_crecimiento: float
    gdd_optimo_diario: float
    dias_descanso_ideal: int
    curva_k: float


def crecimiento_diario_v2(
    gdd_hoy: float,
    fraccion_hidrica: float,
    especie: ParametrosEspecie,
    tipo_suelo: str | None,
    factor_fatiga: float,
) -> float:
    """Crecimiento del día en kg MS/ha.

    tasa_max · f_termico · f_hidrico · f_suelo · f_fatiga

    con f_termico = min(1, gdd_hoy / gdd_optimo_diario) y f_hidrico recortado a
    [0, 1]. Devuelve 0 si `gdd_optimo_diario` no es positivo.
    """
    if especie.gdd_optimo_diario <= 0:
        return 0.0
    f_termico = min(1.0, max(0.0, gdd_hoy) / especie.gdd_optimo_diario)
    f_hidrico = max(0.0, min(1.0, fraccion_hidrica))
    f_suelo = SUELO_FACTOR.get(tipo_suelo, SUELO_FACTOR[None])
    f_fatiga = factor_fatiga
    return especie.tasa_max_crecimiento * f_termico * f_hidrico * f_suelo * f_fatiga
