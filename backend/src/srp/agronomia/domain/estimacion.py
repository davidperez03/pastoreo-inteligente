"""Agregado `EstimacionBiomasa` — raíz del contexto Modelado Agronómico (§17.2).

Orquesta el modelo de crecimiento (§4) y el filtro de Kalman (§5). Mantiene la
memoria de agua en el suelo día a día (bucket model) y emite eventos de dominio
locales cuando la estimación de biomasa cambia.
"""

from __future__ import annotations

from dataclasses import dataclass

from srp.agronomia.domain.crecimiento import ParametrosEspecie, crecimiento_diario_v2
from srp.agronomia.domain.et0 import hargreaves_et0, radiacion_extraterrestre
from srp.agronomia.domain.events import BiomasaRecalculada
from srp.agronomia.domain.hidrico import (
    balance_hidrico_diario,
    fraccion_agua_disponible,
)
from srp.agronomia.domain.kalman import KalmanBiomasa
from srp.agronomia.domain.ndvi_biomasa import biomasa_desde_ndvi
from srp.agronomia.domain.termico import grados_dia
from srp.shared.events import DomainEvent
from srp.shared.types import LecturaNdvi, PotreroId, RegistroClima


@dataclass(frozen=True)
class EstadoSuelo:
    """Propiedades estáticas del suelo/ubicación necesarias para el balance.

    - `capacidad_campo_mm`: agua máxima retenible por el suelo.
    - `tipo_suelo`: textura ("franco"|"arcilloso"|"arenoso"|None).
    - `latitud_grados`: para la radiación extraterrestre (Ra).
    - `factor_fatiga`: memoria de sobrepastoreo del potrero (1.0 = neutro).
    """

    capacidad_campo_mm: float
    tipo_suelo: str | None
    latitud_grados: float
    factor_fatiga: float = 1.0


class EstimacionBiomasa:
    """Estima la biomasa de un potrero fusionando modelo + NDVI.

    El agua del suelo (`suelo_mm`) es estado interno persistente: se arrastra
    entre llamadas a `actualizar_con_clima`, dándole memoria a la transición
    lluvia→sequía.
    """

    def __init__(
        self,
        potrero_id: PotreroId,
        kalman: KalmanBiomasa,
        suelo_actual_mm: float = 0.0,
    ) -> None:
        self._potrero_id = potrero_id
        self._kalman = kalman
        self._suelo_mm = suelo_actual_mm
        self._eventos: list[DomainEvent] = []

    # --- Comandos ---------------------------------------------------------

    def actualizar_con_clima(
        self,
        registro_clima: RegistroClima,
        especie: ParametrosEspecie,
        estado_suelo: EstadoSuelo,
    ) -> float:
        """Paso de predicción diario: GDD + balance hídrico → crecimiento →
        Kalman.predecir. Devuelve la biomasa estimada y emite
        `BiomasaRecalculada(fuente="modelo")`."""
        dia_juliano = registro_clima.fecha.timetuple().tm_yday
        ra = radiacion_extraterrestre(estado_suelo.latitud_grados, dia_juliano)
        et0 = hargreaves_et0(
            registro_clima.temp_max,
            registro_clima.temp_min,
            registro_clima.temp_media,
            ra,
        )
        self._suelo_mm = balance_hidrico_diario(
            self._suelo_mm,
            registro_clima.precipitacion_mm,
            estado_suelo.capacidad_campo_mm,
            et0,
        )
        fraccion = fraccion_agua_disponible(
            self._suelo_mm, estado_suelo.capacidad_campo_mm
        )
        gdd = grados_dia(registro_clima.temp_media, especie.temp_base)
        crecimiento = crecimiento_diario_v2(
            gdd,
            fraccion,
            especie,
            estado_suelo.tipo_suelo,
            estado_suelo.factor_fatiga,
        )
        self._kalman.predecir(crecimiento)
        self._emitir(registro_clima.fecha, "modelo")
        return self._kalman.x

    def corregir_con_ndvi(
        self, lectura: LecturaNdvi, especie: ParametrosEspecie
    ) -> float:
        """Paso de corrección con NDVI: Kalman.actualizar. Las lecturas `stale`
        (reusadas por falta de escena, §6/§11) se ignoran para no reforzar el
        filtro con un dato viejo. Emite `BiomasaRecalculada(fuente="kalman")`
        cuando corrige."""
        if lectura.stale:
            return self._kalman.x
        biomasa_ndvi = biomasa_desde_ndvi(lectura.ndvi_promedio, especie)
        self._kalman.actualizar(biomasa_ndvi, lectura.calidad)
        self._emitir(lectura.fecha, "kalman")
        return self._kalman.x

    # --- Consultas --------------------------------------------------------

    @property
    def potrero_id(self) -> PotreroId:
        return self._potrero_id

    @property
    def biomasa_kg_ms_ha(self) -> float:
        return self._kalman.x

    @property
    def varianza(self) -> float:
        return self._kalman.P

    @property
    def suelo_mm(self) -> float:
        return self._suelo_mm

    def eventos_pendientes(self) -> list[DomainEvent]:
        return list(self._eventos)

    def limpiar_eventos(self) -> None:
        self._eventos.clear()

    # --- Interno ----------------------------------------------------------

    def _emitir(self, fecha, fuente: str) -> None:
        self._eventos.append(
            BiomasaRecalculada(
                potrero_id=self._potrero_id,
                fecha=fecha,
                biomasa_kg_ms_ha=self._kalman.x,
                fuente=fuente,
            )
        )
