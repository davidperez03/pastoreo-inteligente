"""Motor greedy de rotación (§7) — puro, sin DB ni frameworks.

Simula día a día el horizonte: cada lote permanece en su potrero hasta agotar
la biomasa aprovechable o alcanzar MAX_DIAS_PERMANENCIA, y entonces se mueve
al mejor candidato según `score_potrero`. El decaimiento de biomasa es simple:
solo se descuenta el consumo del lote, sin modelo de crecimiento — la
proyección fina de biomasa (crecimiento + Kalman + NDVI) llega con la
integración del contexto agronómico; aquí ese refinamiento sería precisión
falsa sobre un modelo aún no calibrado (§7, §21).

Advertencias (regla f): `Calendario` es un tipo del shared kernel y no se
modifica desde este contexto, así que el motor expone un resultado extendido
`ResultadoRotacion(calendario, advertencias)` vía `optimizar_extendido`; el
método del puerto `optimizar` devuelve solo el `Calendario`.

El LP (PuLP) queda DIFERIDO a la fase 8: entrará como otra implementación del
mismo puerto `OptimizadorRotacion`, con este greedy como fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from srp.rotacion.domain.reglas import (
    MAX_DIAS_PERMANENCIA,
    MIN_DIAS_PERMANENCIA,
    biomasa_aprovechable,
    consumo_diario_lote,
    descanso_cumplido,
    score_potrero,
)
from srp.shared.ports import OptimizadorRotacion
from srp.shared.types import (
    Calendario,
    FincaId,
    LoteId,
    LoteSnapshot,
    Movimiento,
    PotreroId,
    PotreroSnapshot,
)

# Ocupante de un potrero cuyo estado en la proyección es 'ocupado' pero cuyo
# lote no está entre los lotes gestionados (p. ej. ganado ajeno al cálculo).
_OCUPANTE_EXTERNO = "externo"


@dataclass(frozen=True)
class ResultadoRotacion:
    """Calendario más advertencias operativas (sobrepastoreo inminente)."""

    calendario: Calendario
    advertencias: tuple[str, ...] = ()


@dataclass
class _EstadoPotrero:
    """Estado mutable de simulación de un potrero (interno al motor)."""

    snapshot: PotreroSnapshot
    restante_kg: float
    fecha_ultima_salida: date | None
    ocupante: LoteId | str | None = None


@dataclass
class _EstadoLote:
    """Estado mutable de simulación de un lote (interno al motor)."""

    snapshot: LoteSnapshot
    potrero_id: PotreroId | None
    dias_en_potrero: int = 0
    advertido: bool = False
    consumo_diario: float = field(init=False)

    def __post_init__(self) -> None:
        self.consumo_diario = consumo_diario_lote(self.snapshot.ua_equivalente)


class MotorGreedy(OptimizadorRotacion):
    """Implementación greedy del puerto `OptimizadorRotacion` (§7).

    `fecha_inicio` permite simulaciones deterministas en tests; por defecto
    el calendario arranca hoy.
    """

    def __init__(self, fecha_inicio: date | None = None) -> None:
        self._fecha_inicio = fecha_inicio or date.today()

    def optimizar(
        self,
        potreros: list[PotreroSnapshot],
        lotes: list[LoteSnapshot],
        horizonte_dias: int,
    ) -> Calendario:
        return self.optimizar_extendido(potreros, lotes, horizonte_dias).calendario

    def optimizar_extendido(
        self,
        potreros: list[PotreroSnapshot],
        lotes: list[LoteSnapshot],
        horizonte_dias: int,
    ) -> ResultadoRotacion:
        finca_id = self._finca_id(potreros, lotes)
        estado_potreros = self._estado_inicial_potreros(potreros)
        estado_lotes = self._estado_inicial_lotes(lotes, estado_potreros)

        movimientos: list[Movimiento] = []
        advertencias: list[str] = []

        for d in range(horizonte_dias):
            fecha = self._fecha_inicio + timedelta(days=d)
            for lote in estado_lotes:
                self._paso_lote(lote, estado_potreros, fecha, movimientos, advertencias)

        calendario = Calendario(
            finca_id=finca_id,
            horizonte_dias=horizonte_dias,
            movimientos=tuple(movimientos),
        )
        return ResultadoRotacion(calendario=calendario, advertencias=tuple(advertencias))

    # ---- pasos de simulación ----

    def _paso_lote(
        self,
        lote: _EstadoLote,
        potreros: dict[PotreroId, _EstadoPotrero],
        fecha: date,
        movimientos: list[Movimiento],
        advertencias: list[str],
    ) -> None:
        actual = potreros.get(lote.potrero_id) if lote.potrero_id is not None else None

        if self._debe_mover(lote, actual):
            candidatos = self._candidatos(lote, potreros, fecha)
            if candidatos:
                destino = max(
                    candidatos,
                    key=lambda p: (
                        score_potrero(
                            p.restante_kg,
                            p.snapshot.factor_fatiga,
                            p.snapshot.fuente_agua,
                        ),
                        p.snapshot.nombre,  # desempate determinista
                    ),
                )
                self._mover(lote, actual, destino, fecha, movimientos)
            elif not lote.advertido:
                lote.advertido = True
                if actual is not None:
                    advertencias.append(
                        f"{fecha.isoformat()}: lote {lote.snapshot.id} sin potrero "
                        f"candidato; permanece en '{actual.snapshot.nombre}' — "
                        "sobrepastoreo inminente"
                    )
                else:
                    advertencias.append(
                        f"{fecha.isoformat()}: lote {lote.snapshot.id} sin potrero "
                        "asignado y sin candidato disponible"
                    )

        # Consumo del día en el potrero donde termina el lote (si tiene).
        ocupado = potreros.get(lote.potrero_id) if lote.potrero_id is not None else None
        if ocupado is not None:
            ocupado.restante_kg = max(0.0, ocupado.restante_kg - lote.consumo_diario)
            lote.dias_en_potrero += 1

    @staticmethod
    def _debe_mover(lote: _EstadoLote, actual: _EstadoPotrero | None) -> bool:
        if actual is None:
            return True  # lote sin potrero: hay que asignarle uno
        if lote.dias_en_potrero >= MAX_DIAS_PERMANENCIA:
            return True
        # Biomasa aprovechable agotada: no alcanza ni para el consumo de hoy.
        return actual.restante_kg < lote.consumo_diario

    def _candidatos(
        self,
        lote: _EstadoLote,
        potreros: dict[PotreroId, _EstadoPotrero],
        fecha: date,
    ) -> list[_EstadoPotrero]:
        minimo_kg = MIN_DIAS_PERMANENCIA * lote.consumo_diario
        return [
            p
            for p in potreros.values()
            if p.snapshot.id != lote.potrero_id  # no "moverse" al mismo potrero
            and p.ocupante is None  # no ocupado por otro lote
            and descanso_cumplido(
                p.fecha_ultima_salida, fecha, p.snapshot.dias_descanso_ideal
            )
            and p.restante_kg >= minimo_kg
        ]

    @staticmethod
    def _mover(
        lote: _EstadoLote,
        origen: _EstadoPotrero | None,
        destino: _EstadoPotrero,
        fecha: date,
        movimientos: list[Movimiento],
    ) -> None:
        if origen is not None:
            origen.ocupante = None
            origen.fecha_ultima_salida = fecha
        destino.ocupante = lote.snapshot.id
        lote.potrero_id = destino.snapshot.id
        lote.dias_en_potrero = 0
        lote.advertido = False
        movimientos.append(
            Movimiento(lote_id=lote.snapshot.id, potrero_id=destino.snapshot.id, fecha=fecha)
        )

    # ---- estado inicial ----

    @staticmethod
    def _estado_inicial_potreros(
        potreros: list[PotreroSnapshot],
    ) -> dict[PotreroId, _EstadoPotrero]:
        return {
            p.id: _EstadoPotrero(
                snapshot=p,
                restante_kg=biomasa_aprovechable(p.biomasa_kg_ms_ha, p.area_ha),
                fecha_ultima_salida=p.fecha_ultima_salida,
                # 'ocupado' sin lote conocido => ocupante externo (nunca candidato);
                # si un lote gestionado está ahí, se reasigna en _estado_inicial_lotes.
                ocupante=_OCUPANTE_EXTERNO if p.estado == "ocupado" else None,
            )
            for p in potreros
        }

    @staticmethod
    def _estado_inicial_lotes(
        lotes: list[LoteSnapshot],
        potreros: dict[PotreroId, _EstadoPotrero],
    ) -> list[_EstadoLote]:
        estados: list[_EstadoLote] = []
        for lote in lotes:
            potrero_id = lote.potrero_actual_id
            if potrero_id is not None and potrero_id in potreros:
                potreros[potrero_id].ocupante = lote.id
            else:
                potrero_id = None  # potrero fuera de la finca/proyección
            estados.append(_EstadoLote(snapshot=lote, potrero_id=potrero_id))
        return estados

    @staticmethod
    def _finca_id(
        potreros: list[PotreroSnapshot], lotes: list[LoteSnapshot]
    ) -> FincaId:
        if potreros:
            return potreros[0].finca_id
        if lotes:
            return lotes[0].finca_id
        raise ValueError("Se requiere al menos un potrero o lote para optimizar")
