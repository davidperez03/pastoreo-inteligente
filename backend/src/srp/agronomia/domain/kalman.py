"""Filtro de Kalman escalar para fusión modelo + NDVI — §5.

Se trata la biomasa como un estado a estimar: el modelo agronómico *predice*
(paso de tiempo) y el NDVI *observa* (corrección). El filtro combina ambos
ponderando por su incertidumbre — el estándar de fusión modelo+sensor remoto
en agricultura de precisión.
"""

from __future__ import annotations


class KalmanBiomasa:
    """Filtro de Kalman 1-D sobre la biomasa (kg MS/ha).

    Estado `x` = biomasa estimada; `P` = varianza del estado. `Q` y `R` son
    puntos de partida fijos; deberían calibrarse por especie/región con ciclos
    reales (fase 6-7), no tratarse como constantes universales.
    """

    Q = 5.0  # ruido del proceso (incertidumbre del modelo)
    R = 15.0  # ruido de observación (incertidumbre del NDVI)

    def __init__(self, biomasa_inicial: float, varianza_inicial: float = 100.0) -> None:
        self.x = biomasa_inicial
        self.P = varianza_inicial

    def predecir(self, crecimiento_estimado_dia: float) -> float:
        """Paso de predicción: avanza el estado con el crecimiento del modelo
        y aumenta la incertidumbre en Q."""
        self.x = self.x + crecimiento_estimado_dia
        self.P = self.P + self.Q
        return self.x

    def actualizar(
        self, biomasa_desde_ndvi: float, calidad_lectura: float = 1.0
    ) -> float:
        """Paso de corrección con la observación NDVI.

        `R_ajustado = R / max(calidad, 0.05)`: una lectura de baja calidad
        (nubosidad alta) infla su ruido de observación, de modo que apenas
        mueve el estado. El guard evita la división por ~0.
        """
        r_ajustado = self.R / max(calidad_lectura, 0.05)
        k = self.P / (self.P + r_ajustado)
        self.x = self.x + k * (biomasa_desde_ndvi - self.x)
        self.P = (1.0 - k) * self.P
        return self.x
