"""Tests puros del dominio de Gestión de Ganado: sin base de datos, sin bus."""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import fields
from datetime import date

import pytest

from srp.ganado.domain.entities import LoteGanado
from srp.ganado.domain.errors import DomainError
from srp.ganado.domain.events import LoteEntroAPotrero, LoteSalioDePotrero
from srp.shared.events import DomainEvent
from srp.shared.types import FincaId, LoteId, PotreroId


def _lote(**kwargs) -> LoteGanado:
    defaults = dict(
        id=LoteId(uuid.uuid4()),
        finca_id=FincaId(uuid.uuid4()),
        nombre="Lote Norte",
        n_animales=20,
        peso_promedio_kg=450.0,
    )
    defaults.update(kwargs)
    return LoteGanado(**defaults)


class TestUAEquivalente:
    def test_20_animales_de_450_kg_son_20_ua(self):
        assert _lote(n_animales=20, peso_promedio_kg=450.0).ua_equivalente == 20.0

    def test_formula_general(self):
        # 30 animales × 300 kg / 450 = 20 UA
        assert _lote(n_animales=30, peso_promedio_kg=300.0).ua_equivalente == 20.0


class TestValidaciones:
    def test_n_animales_no_positivo(self):
        with pytest.raises(DomainError):
            _lote(n_animales=0)

    def test_peso_no_positivo(self):
        with pytest.raises(DomainError):
            _lote(peso_promedio_kg=0)


class TestEntradaAPotrero:
    def test_entrada_fija_potrero_y_emite_evento(self):
        lote = _lote()
        potrero_id = PotreroId(uuid.uuid4())
        lote.entrar_a_potrero(potrero_id, date(2026, 7, 1), biomasa_inicial=2800.0)

        assert lote.potrero_actual_id == potrero_id
        eventos = lote.eventos_pendientes()
        assert eventos == [
            LoteEntroAPotrero(
                potrero_id=potrero_id,
                lote_id=lote.id,
                fecha=date(2026, 7, 1),
                biomasa_inicial=2800.0,
            )
        ]
        assert isinstance(eventos[0], DomainEvent)

    def test_entrada_estando_ya_en_potrero_lanza_domain_error(self):
        lote = _lote()
        lote.entrar_a_potrero(PotreroId(uuid.uuid4()), date(2026, 7, 1))
        with pytest.raises(DomainError):
            lote.entrar_a_potrero(PotreroId(uuid.uuid4()), date(2026, 7, 2))


class TestSalidaDePotrero:
    def test_salida_sin_estar_en_potrero_lanza_domain_error(self):
        with pytest.raises(DomainError):
            _lote().salir_de_potrero(date(2026, 7, 10), biomasa_final=1500.0)

    def test_salida_limpia_potrero_y_emite_evento(self):
        lote = _lote()
        potrero_id = PotreroId(uuid.uuid4())
        lote.entrar_a_potrero(potrero_id, date(2026, 7, 1), biomasa_inicial=2800.0)
        lote.limpiar_eventos()

        lote.salir_de_potrero(date(2026, 7, 5), biomasa_final=1500.0)

        assert lote.potrero_actual_id is None
        assert lote.eventos_pendientes() == [
            LoteSalioDePotrero(
                potrero_id=potrero_id,
                lote_id=lote.id,
                fecha=date(2026, 7, 5),
                biomasa_inicial=2800.0,
                biomasa_final=1500.0,
            )
        ]


class TestFirmasDeEventos:
    """Las firmas son contrato público entre contextos: nombres y orden."""

    def test_firma_lote_entro_a_potrero(self):
        assert [f.name for f in fields(LoteEntroAPotrero)] == [
            "potrero_id",
            "lote_id",
            "fecha",
            "biomasa_inicial",
        ]

    def test_firma_lote_salio_de_potrero(self):
        assert [f.name for f in fields(LoteSalioDePotrero)] == [
            "potrero_id",
            "lote_id",
            "fecha",
            "biomasa_inicial",
            "biomasa_final",
        ]

    def test_eventos_son_frozen(self):
        evento = LoteEntroAPotrero(
            PotreroId(uuid.uuid4()), LoteId(uuid.uuid4()), date.today(), None
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            evento.fecha = date(2000, 1, 1)  # type: ignore[misc]
