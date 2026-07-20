"""Tipos compartidos del shared kernel.

Estos tipos son el vocabulario común entre contextos. Los contextos NO deben
importar nada de otro contexto: solo de `srp.shared` (ver §17-§18 de la spec).
Los agregados ricos (Potrero, LoteGanado, EstimacionBiomasa) viven en su propio
contexto; aquí solo hay value objects y snapshots planos para cruzar fronteras.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import NewType

OrganizacionId = NewType("OrganizacionId", uuid.UUID)
FincaId = NewType("FincaId", uuid.UUID)
PotreroId = NewType("PotreroId", uuid.UUID)
LoteId = NewType("LoteId", uuid.UUID)


@dataclass(frozen=True)
class Coordenada:
    lat: float
    lng: float


@dataclass(frozen=True)
class RegistroClima:
    fecha: date
    temp_media: float
    temp_max: float
    temp_min: float
    precipitacion_mm: float
    humedad_suelo_pct: float | None = None
    # True cuando el dato es un fallback (último-conocido) y no una lectura real (§11)
    estimado: bool = False


@dataclass(frozen=True)
class LecturaNdvi:
    fecha: date
    ndvi_promedio: float
    # 0..1 — derivada de nubosidad; ajusta el ruido de observación del Kalman (§5)
    calidad: float = 1.0
    fuente: str = "sentinel-2"
    # True cuando no hubo escena utilizable y se reusó la última lectura (§6, §11)
    stale: bool = False


@dataclass(frozen=True)
class PotreroSnapshot:
    """Proyección plana de un potrero para cruzar fronteras de contexto
    (p. ej. el optimizador de rotación no necesita el agregado completo)."""

    id: PotreroId
    finca_id: FincaId
    nombre: str
    area_ha: float
    estado: str  # 'descanso' | 'ocupado' | 'listo'
    biomasa_kg_ms_ha: float | None
    factor_fatiga: float
    dias_descanso_ideal: int
    fecha_ultima_salida: date | None
    fuente_agua: bool = False


@dataclass(frozen=True)
class LoteSnapshot:
    id: LoteId
    finca_id: FincaId
    n_animales: int
    ua_equivalente: float
    potrero_actual_id: PotreroId | None


@dataclass(frozen=True)
class Movimiento:
    lote_id: LoteId
    potrero_id: PotreroId
    fecha: date


@dataclass(frozen=True)
class Calendario:
    """Resultado de una optimización/sugerencia de rotación."""

    finca_id: FincaId
    horizonte_dias: int
    movimientos: tuple[Movimiento, ...] = field(default_factory=tuple)
