"""Tests puros del MotorGreedy (§7) con escenarios sintéticos — sin DB."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from srp.rotacion.domain.motor import MotorGreedy
from srp.rotacion.domain.reglas import (
    CONSUMO_UA_KG_MS,
    MAX_DIAS_PERMANENCIA,
    MIN_DIAS_PERMANENCIA,
    UTILIZACION,
    biomasa_aprovechable,
    consumo_diario_lote,
    dias_de_descanso,
)
from srp.shared.types import FincaId, LoteId, LoteSnapshot, PotreroId, PotreroSnapshot

INICIO = date(2026, 7, 20)
FINCA = FincaId(uuid.uuid4())


def potrero(
    nombre: str,
    biomasa: float | None = 3000.0,
    factor_fatiga: float = 1.0,
    estado: str = "descanso",
    dias_descanso_ideal: int = 28,
    fecha_ultima_salida: date | None = None,
    fuente_agua: bool = False,
    area_ha: float = 2.0,
) -> PotreroSnapshot:
    return PotreroSnapshot(
        id=PotreroId(uuid.uuid4()),
        finca_id=FINCA,
        nombre=nombre,
        area_ha=area_ha,
        estado=estado,
        biomasa_kg_ms_ha=biomasa,
        factor_fatiga=factor_fatiga,
        dias_descanso_ideal=dias_descanso_ideal,
        fecha_ultima_salida=fecha_ultima_salida,
        fuente_agua=fuente_agua,
    )


def lote(ua: float = 10.0, potrero_actual: PotreroId | None = None) -> LoteSnapshot:
    return LoteSnapshot(
        id=LoteId(uuid.uuid4()),
        finca_id=FINCA,
        n_animales=int(ua),
        ua_equivalente=ua,
        potrero_actual_id=potrero_actual,
    )


def test_reglas_auxiliares():
    assert dias_de_descanso(None, INICIO) is None
    assert dias_de_descanso(INICIO - timedelta(days=10), INICIO) == 10
    assert biomasa_aprovechable(3000.0, 2.0) == 3000.0 * 2.0 * UTILIZACION
    assert biomasa_aprovechable(None, 2.0) == 0.0
    assert consumo_diario_lote(10.0) == 10.0 * CONSUMO_UA_KG_MS


def test_elige_potrero_con_mayor_biomasa_por_fatiga():
    """(1) De 3 potreros, gana el de mayor biomasa * factor_fatiga."""
    p1 = potrero("A", biomasa=2000, factor_fatiga=1.0)
    p2 = potrero("B", biomasa=4000, factor_fatiga=1.0)  # mejor score
    p3 = potrero("C", biomasa=3000, factor_fatiga=0.9)
    resultado = MotorGreedy(INICIO).optimizar_extendido([p1, p2, p3], [lote()], 10)
    movs = resultado.calendario.movimientos
    assert movs, "el lote sin potrero debe recibir asignación el día 0"
    assert movs[0].potrero_id == p2.id
    assert movs[0].fecha == INICIO


def test_descanso_insuficiente_no_es_candidato():
    """(2) Un potrero sin descanso cumplido no es candidato aunque tenga más biomasa."""
    reciente = potrero(
        "MuchoPasto",
        biomasa=9000,
        dias_descanso_ideal=28,
        fecha_ultima_salida=INICIO - timedelta(days=5),
    )
    descansado = potrero("Descansado", biomasa=2500)
    resultado = MotorGreedy(INICIO).optimizar_extendido([reciente, descansado], [lote()], 5)
    movs = resultado.calendario.movimientos
    assert movs
    assert movs[0].potrero_id == descansado.id
    assert all(m.potrero_id != reciente.id for m in movs)


def test_potrero_fatigado_pierde_contra_sano():
    """(3) factor_fatiga 0.6 pierde contra 1.0 con biomasa similar."""
    fatigado = potrero("Fatigado", biomasa=3100, factor_fatiga=0.6)
    sano = potrero("Sano", biomasa=3000, factor_fatiga=1.0)
    resultado = MotorGreedy(INICIO).optimizar_extendido([fatigado, sano], [lote()], 3)
    assert resultado.calendario.movimientos[0].potrero_id == sano.id


def test_dos_lotes_nunca_comparten_potrero_el_mismo_dia():
    """(4) Ningún potrero aloja dos lotes el mismo día en todo el horizonte."""
    horizonte = 20
    potreros = [potrero(f"P{i}", biomasa=2500 + 100 * i) for i in range(4)]
    lotes = [lote(ua=8.0), lote(ua=8.0)]
    resultado = MotorGreedy(INICIO).optimizar_extendido(potreros, lotes, horizonte)
    movs = resultado.calendario.movimientos
    assert movs

    # Reconstruye la ocupación día a día desde los movimientos.
    ubicacion: dict[uuid.UUID, uuid.UUID | None] = {lo.id: None for lo in lotes}
    por_fecha: dict[date, list] = {}
    for m in movs:
        por_fecha.setdefault(m.fecha, []).append(m)
    for d in range(horizonte):
        fecha = INICIO + timedelta(days=d)
        for m in por_fecha.get(fecha, []):
            ubicacion[m.lote_id] = m.potrero_id
        ocupados = [p for p in ubicacion.values() if p is not None]
        assert len(ocupados) == len(set(ocupados)), f"potrero compartido el {fecha}"


def test_sin_candidatos_advierte_sin_fallar():
    """(5) Sin candidatos válidos: advertencia de sobrepastoreo, no crash."""
    actual = potrero("Actual", biomasa=50.0, area_ha=1.0)  # casi agotado
    en_descanso = potrero(
        "EnDescanso",
        biomasa=8000,
        fecha_ultima_salida=INICIO - timedelta(days=2),
        dias_descanso_ideal=40,
    )
    lo = lote(ua=10.0, potrero_actual=actual.id)
    resultado = MotorGreedy(INICIO).optimizar_extendido([actual, en_descanso], [lo], 10)
    assert resultado.calendario.movimientos == ()
    assert resultado.advertencias
    assert "sobrepastoreo" in resultado.advertencias[0]


def test_respeta_min_y_max_dias_permanencia():
    """(6) Con biomasa abundante, las estancias duran entre MIN y MAX días."""
    horizonte = 30
    potreros = [potrero(f"P{i}", biomasa=6000, area_ha=3.0) for i in range(5)]
    lo = lote(ua=10.0)
    resultado = MotorGreedy(INICIO).optimizar_extendido(potreros, [lo], horizonte)
    movs = resultado.calendario.movimientos
    assert len(movs) >= 2
    fechas = [m.fecha for m in movs]
    estancias = [(b - a).days for a, b in zip(fechas, fechas[1:], strict=False)]
    assert estancias, "debe haber al menos un cambio de potrero"
    for dur in estancias:
        assert MIN_DIAS_PERMANENCIA <= dur <= MAX_DIAS_PERMANENCIA
    # Con biomasa de sobra, la estancia debe llegar al tope, no cortarse antes.
    assert estancias[0] == MAX_DIAS_PERMANENCIA


def test_potrero_ocupado_externamente_no_es_candidato():
    """Un potrero 'ocupado' cuyo lote no está en la proyección nunca es destino."""
    ajeno = potrero("Ajeno", biomasa=9000, estado="ocupado")
    libre = potrero("Libre", biomasa=2000)
    resultado = MotorGreedy(INICIO).optimizar_extendido([ajeno, libre], [lote()], 10)
    assert all(m.potrero_id != ajeno.id for m in resultado.calendario.movimientos)


def test_sin_potreros_ni_lotes_lanza_error():
    with pytest.raises(ValueError):
        MotorGreedy(INICIO).optimizar([], [], 10)
