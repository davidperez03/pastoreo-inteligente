"""Integración en memoria: bus -> handler -> repo fake (§17).

Publicar `LoteSalioDePotrero` debe actualizar el estado del potrero vía el
handler, sin que ningún contexto toque las tablas de otro.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from srp.calibracion.application.handler import (
    CalibrarPotreroAlSalirLote,
    registrar_en_bus,
)
from srp.calibracion.domain.events import LoteSalioDePotrero
from srp.shared.events import BusEventosEnMemoria
from srp.shared.types import PotreroId


class RepoFake:
    """Repositorio en memoria que implementa el puerto RepositorioCalibracion."""

    def __init__(self, estados: dict[uuid.UUID, tuple[float, int, float | None]]):
        self.estados = estados
        self.guardados: list[tuple[uuid.UUID, float, int]] = []

    async def leer_estado(self, potrero_id):
        return self.estados.get(potrero_id)

    async def guardar_estado(self, potrero_id, factor, n_ciclos):
        self.guardados.append((potrero_id, factor, n_ciclos))
        _, _, biomasa = self.estados[potrero_id]
        self.estados[potrero_id] = (factor, n_ciclos, biomasa)


@pytest.fixture
def potrero_id() -> PotreroId:
    return PotreroId(uuid.uuid4())


async def test_publicar_evento_calibra_el_potrero(bus, potrero_id):
    repo = RepoFake({potrero_id: (1.0, 0, 100.0)})
    handler = CalibrarPotreroAlSalirLote(repo)
    registrar_en_bus(bus, handler)

    await bus.publicar(
        [
            LoteSalioDePotrero(
                potrero_id=potrero_id,
                lote_id=None,
                fecha=date(2026, 7, 20),
                biomasa_inicial=2500.0,
                biomasa_final=80.0,
            )
        ]
    )

    # error_relativo = 80/100 = 0.8; n_ciclos=0 -> factor salta a 0.8, ciclos=1.
    assert repo.guardados == [(potrero_id, pytest.approx(0.8), 1)]
    assert repo.estados[potrero_id] == (pytest.approx(0.8), 1, 100.0)


async def test_evento_sin_biomasa_final_no_calibra(bus, potrero_id):
    repo = RepoFake({potrero_id: (1.0, 3, 100.0)})
    registrar_en_bus(bus, CalibrarPotreroAlSalirLote(repo))

    await bus.publicar(
        [
            LoteSalioDePotrero(
                potrero_id=potrero_id,
                lote_id=None,
                fecha=date(2026, 7, 20),
                biomasa_inicial=2500.0,
                biomasa_final=None,
            )
        ]
    )

    assert repo.guardados == []


async def test_evento_sin_biomasa_predicha_no_calibra(bus, potrero_id):
    repo = RepoFake({potrero_id: (1.0, 3, None)})
    registrar_en_bus(bus, CalibrarPotreroAlSalirLote(repo))

    await bus.publicar(
        [
            LoteSalioDePotrero(
                potrero_id=potrero_id,
                lote_id=None,
                fecha=date(2026, 7, 20),
                biomasa_inicial=2500.0,
                biomasa_final=80.0,
            )
        ]
    )

    assert repo.guardados == []


async def test_potrero_inexistente_no_calibra(bus, potrero_id):
    repo = RepoFake({})  # sin estado para el potrero
    registrar_en_bus(bus, CalibrarPotreroAlSalirLote(repo))

    await bus.publicar(
        [
            LoteSalioDePotrero(
                potrero_id=potrero_id,
                lote_id=None,
                fecha=date(2026, 7, 20),
                biomasa_inicial=None,
                biomasa_final=80.0,
            )
        ]
    )

    assert repo.guardados == []
