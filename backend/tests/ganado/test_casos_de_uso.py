"""Tests de los casos de uso con fakes en memoria y bus espía (§14)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from srp.ganado.application.errors import LoteNoEncontrado
from srp.ganado.application.use_cases import (
    CrearLote,
    ListarLotes,
    RegistrarEntrada,
    RegistrarSalida,
)
from srp.ganado.domain.entities import EventoPastoreo, LoteGanado
from srp.ganado.domain.errors import DomainError
from srp.ganado.domain.events import LoteEntroAPotrero, LoteSalioDePotrero
from srp.ganado.domain.ports.eventos_pastoreo_repository import EventosPastoreoRepository
from srp.ganado.domain.ports.lote_repository import LoteRepository
from srp.shared.events import DomainEvent
from srp.shared.ports import PublicadorEventos
from srp.shared.types import FincaId, LoteId, PotreroId


class FakeLoteRepository(LoteRepository):
    def __init__(self) -> None:
        self.lotes: dict[uuid.UUID, LoteGanado] = {}

    async def guardar(self, lote: LoteGanado) -> None:
        self.lotes[lote.id] = lote

    async def obtener(self, lote_id: LoteId) -> LoteGanado | None:
        return self.lotes.get(lote_id)

    async def listar_por_finca(self, finca_id: FincaId) -> list[LoteGanado]:
        return [lote for lote in self.lotes.values() if lote.finca_id == finca_id]


class FakeEventosPastoreoRepository(EventosPastoreoRepository):
    def __init__(self) -> None:
        self.eventos: dict[uuid.UUID, EventoPastoreo] = {}

    async def abrir_evento(self, lote_id, potrero_id, fecha_entrada, biomasa_inicial):
        evento = EventoPastoreo(
            id=uuid.uuid4(),
            lote_id=lote_id,
            potrero_id=potrero_id,
            fecha_entrada=fecha_entrada,
            biomasa_inicial=biomasa_inicial,
        )
        self.eventos[evento.id] = evento
        return evento

    async def cerrar_evento(self, evento_id, fecha_salida, biomasa_final):
        abierto = self.eventos[evento_id]
        cerrado = EventoPastoreo(
            id=abierto.id,
            lote_id=abierto.lote_id,
            potrero_id=abierto.potrero_id,
            fecha_entrada=abierto.fecha_entrada,
            fecha_salida=fecha_salida,
            biomasa_inicial=abierto.biomasa_inicial,
            biomasa_final=biomasa_final,
        )
        self.eventos[evento_id] = cerrado
        return cerrado

    async def evento_abierto_de_lote(self, lote_id):
        for evento in self.eventos.values():
            if evento.lote_id == lote_id and evento.abierto:
                return evento
        return None


class BusEspia(PublicadorEventos):
    def __init__(self) -> None:
        self.publicados: list[DomainEvent] = []

    async def publicar(self, eventos: list[DomainEvent]) -> None:
        self.publicados.extend(eventos)


@pytest.fixture
def lotes_repo() -> FakeLoteRepository:
    return FakeLoteRepository()


@pytest.fixture
def eventos_repo() -> FakeEventosPastoreoRepository:
    return FakeEventosPastoreoRepository()


@pytest.fixture
def bus_espia() -> BusEspia:
    return BusEspia()


async def test_crear_lote_persiste_y_devuelve_dto(lotes_repo):
    finca_id = FincaId(uuid.uuid4())
    dto = await CrearLote(lotes_repo).ejecutar(finca_id, "Lote A", 20, 450.0)

    assert dto.finca_id == finca_id
    assert dto.ua_equivalente == 20.0
    assert dto.potrero_actual_id is None
    assert dto.id in lotes_repo.lotes


async def test_crear_lote_invalido_lanza_domain_error(lotes_repo):
    with pytest.raises(DomainError):
        await CrearLote(lotes_repo).ejecutar(FincaId(uuid.uuid4()), "Lote A", -5, 450.0)


async def test_listar_lotes_filtra_por_finca(lotes_repo):
    finca_a = FincaId(uuid.uuid4())
    finca_b = FincaId(uuid.uuid4())
    await CrearLote(lotes_repo).ejecutar(finca_a, "A1", 10, 400.0)
    await CrearLote(lotes_repo).ejecutar(finca_b, "B1", 5, 350.0)

    dtos = await ListarLotes(lotes_repo).ejecutar(finca_a)
    assert [d.nombre for d in dtos] == ["A1"]


async def test_registrar_entrada_abre_evento_y_publica(lotes_repo, eventos_repo, bus_espia):
    finca_id = FincaId(uuid.uuid4())
    lote = await CrearLote(lotes_repo).ejecutar(finca_id, "Lote A", 20, 450.0)
    potrero_id = PotreroId(uuid.uuid4())

    caso = RegistrarEntrada(lotes_repo, eventos_repo, bus_espia)
    evento = await caso.ejecutar(
        LoteId(lote.id), potrero_id, date(2026, 7, 1), biomasa_inicial=2800.0
    )

    # Fila abierta en eventos_pastoreo
    assert evento.fecha_entrada == date(2026, 7, 1)
    assert evento.fecha_salida is None
    assert evento.biomasa_inicial == 2800.0
    # potrero_actual_id actualizado
    assert lotes_repo.lotes[lote.id].potrero_actual_id == potrero_id
    # Evento de dominio publicado con la firma correcta
    assert bus_espia.publicados == [
        LoteEntroAPotrero(
            potrero_id=potrero_id,
            lote_id=LoteId(lote.id),
            fecha=date(2026, 7, 1),
            biomasa_inicial=2800.0,
        )
    ]


async def test_registrar_entrada_usa_fecha_hoy_por_defecto(lotes_repo, eventos_repo, bus_espia):
    lote = await CrearLote(lotes_repo).ejecutar(FincaId(uuid.uuid4()), "A", 10, 400.0)
    evento = await RegistrarEntrada(lotes_repo, eventos_repo, bus_espia).ejecutar(
        LoteId(lote.id), PotreroId(uuid.uuid4())
    )
    assert evento.fecha_entrada == date.today()


async def test_registrar_entrada_lote_inexistente(lotes_repo, eventos_repo, bus_espia):
    with pytest.raises(LoteNoEncontrado):
        await RegistrarEntrada(lotes_repo, eventos_repo, bus_espia).ejecutar(
            LoteId(uuid.uuid4()), PotreroId(uuid.uuid4())
        )
    assert bus_espia.publicados == []


async def test_registrar_entrada_doble_lanza_y_no_publica(lotes_repo, eventos_repo, bus_espia):
    lote = await CrearLote(lotes_repo).ejecutar(FincaId(uuid.uuid4()), "A", 10, 400.0)
    caso = RegistrarEntrada(lotes_repo, eventos_repo, bus_espia)
    await caso.ejecutar(LoteId(lote.id), PotreroId(uuid.uuid4()), date(2026, 7, 1))
    bus_espia.publicados.clear()

    with pytest.raises(DomainError):
        await caso.ejecutar(LoteId(lote.id), PotreroId(uuid.uuid4()), date(2026, 7, 2))

    assert bus_espia.publicados == []
    assert len(eventos_repo.eventos) == 1  # no se abrió una segunda fila


async def test_registrar_salida_cierra_evento_y_publica(lotes_repo, eventos_repo, bus_espia):
    lote = await CrearLote(lotes_repo).ejecutar(FincaId(uuid.uuid4()), "A", 20, 450.0)
    potrero_id = PotreroId(uuid.uuid4())
    await RegistrarEntrada(lotes_repo, eventos_repo, bus_espia).ejecutar(
        LoteId(lote.id), potrero_id, date(2026, 7, 1), biomasa_inicial=2800.0
    )
    bus_espia.publicados.clear()

    evento = await RegistrarSalida(lotes_repo, eventos_repo, bus_espia).ejecutar(
        LoteId(lote.id), date(2026, 7, 5), biomasa_final=1500.0
    )

    # Fila cerrada con biomasa_final
    assert evento.fecha_salida == date(2026, 7, 5)
    assert evento.biomasa_final == 1500.0
    # potrero_actual_id en NULL
    assert lotes_repo.lotes[lote.id].potrero_actual_id is None
    # Evento de dominio con firma correcta (incluye biomasa_inicial del ciclo)
    assert bus_espia.publicados == [
        LoteSalioDePotrero(
            potrero_id=potrero_id,
            lote_id=LoteId(lote.id),
            fecha=date(2026, 7, 5),
            biomasa_inicial=2800.0,
            biomasa_final=1500.0,
        )
    ]


async def test_registrar_salida_sin_estar_en_potrero(lotes_repo, eventos_repo, bus_espia):
    lote = await CrearLote(lotes_repo).ejecutar(FincaId(uuid.uuid4()), "A", 10, 400.0)
    with pytest.raises(DomainError):
        await RegistrarSalida(lotes_repo, eventos_repo, bus_espia).ejecutar(
            LoteId(lote.id), date(2026, 7, 5)
        )
    assert bus_espia.publicados == []
