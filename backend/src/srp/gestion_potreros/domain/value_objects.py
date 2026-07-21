"""Value objects del contexto Gestión de Potreros (§17.2)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from srp.gestion_potreros.domain.excepciones import DomainError
from srp.shared.types import Coordenada

FACTOR_FATIGA_MIN = 0.5
FACTOR_FATIGA_MAX = 1.3


class EstadoPotrero(StrEnum):
    """Estados del ciclo de pastoreo de un potrero (CHECK de §2)."""

    DESCANSO = "descanso"
    OCUPADO = "ocupado"
    LISTO = "listo"


@dataclass(frozen=True)
class Geometria:
    """Polígono levantado en campo o importado de planimetría (§3).

    `puntos` son coordenadas WGS84 (lat, lng) del anillo exterior, sin cerrar
    (el primer punto no se repite al final). El cálculo de área geodésica es
    responsabilidad del puerto `GeometriaValidator` del shared kernel, no de
    este VO — el dominio no importa librerías geoespaciales (§18.4).
    """

    puntos: tuple[Coordenada, ...]
    metodo_levantamiento: str  # 'gps_app' | 'dxf' | 'kml' | 'gpx' | 'manual'...
    accuracy_m: float | None = None

    def __post_init__(self) -> None:
        if len(self.puntos) < 3:
            raise DomainError("Una geometría de potrero requiere al menos 3 puntos")
        if not self.metodo_levantamiento:
            raise DomainError("La geometría requiere el método de levantamiento")


@dataclass(frozen=True)
class FactorFatiga:
    """Factor multiplicativo de recuperación del potrero (§8).

    Acotado al rango [0.5, 1.3] — mismo CHECK que la columna de §2: el clamp
    en el VO garantiza que ningún camino del dominio produzca un valor que la
    base de datos rechazaría.
    """

    valor: float

    def __post_init__(self) -> None:
        acotado = min(max(float(self.valor), FACTOR_FATIGA_MIN), FACTOR_FATIGA_MAX)
        object.__setattr__(self, "valor", acotado)

    @classmethod
    def neutro(cls) -> FactorFatiga:
        return cls(1.0)
