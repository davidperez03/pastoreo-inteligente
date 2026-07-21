"""Caso de uso: sugerir un calendario de rotación para una finca (§7, §9).

Lecturas vía proyección CQRS (§19.1): este contexto no escribe nada ni carga
agregados de otros contextos — consume snapshots planos del shared kernel a
través del puerto local `ProyeccionRotacion`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from srp.rotacion.domain.motor import ResultadoRotacion
from srp.shared.ports import OptimizadorRotacion
from srp.shared.types import Calendario, FincaId, LoteSnapshot, PotreroSnapshot


class ProyeccionRotacion(ABC):
    """Puerto de salida (local al contexto): proyección de solo lectura con
    los snapshots que necesita el optimizador."""

    @abstractmethod
    async def potreros_de_finca(self, finca_id: FincaId) -> list[PotreroSnapshot]: ...

    @abstractmethod
    async def lotes_de_finca(self, finca_id: FincaId) -> list[LoteSnapshot]: ...


class SugerirRotacion:
    """Obtiene los snapshots de la finca y delega en el optimizador (puerto
    `OptimizadorRotacion`: hoy `MotorGreedy`, en fase 8 el LP con este greedy
    como fallback)."""

    def __init__(
        self, proyeccion: ProyeccionRotacion, optimizador: OptimizadorRotacion
    ) -> None:
        self._proyeccion = proyeccion
        self._optimizador = optimizador

    async def ejecutar(self, finca_id: FincaId, horizonte_dias: int) -> ResultadoRotacion:
        potreros = await self._proyeccion.potreros_de_finca(finca_id)
        lotes = await self._proyeccion.lotes_de_finca(finca_id)

        # Finca sin potreros ni lotes visibles (o fuera de la organización,
        # que con RLS se ve idéntico): calendario vacío, sin error.
        if not potreros and not lotes:
            return ResultadoRotacion(
                calendario=Calendario(finca_id=finca_id, horizonte_dias=horizonte_dias)
            )

        # Si el optimizador ofrece el resultado extendido (advertencias de
        # sobrepastoreo, regla f de §7), lo preferimos; el puerto base solo
        # garantiza `optimizar` -> Calendario.
        extendido = getattr(self._optimizador, "optimizar_extendido", None)
        if callable(extendido):
            return extendido(potreros, lotes, horizonte_dias)
        calendario = self._optimizador.optimizar(potreros, lotes, horizonte_dias)
        return ResultadoRotacion(calendario=calendario)
