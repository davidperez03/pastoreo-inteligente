"""Tests de casos de uso con fakes (§14): repositorio en memoria, validador
fake y bus espía — sin infraestructura real."""

from __future__ import annotations

import uuid

import pytest

from srp.gestion_potreros.application.dto import (
    ImportarPlanimetriaCommand,
    RegistrarPotreroManualCommand,
)
from srp.gestion_potreros.application.use_cases.importar_planimetria import (
    ImportarPlanimetria,
    puntos_desde_geojson,
)
from srp.gestion_potreros.application.use_cases.listar_potreros import (
    ListarPotreros,
    ObtenerPotrero,
)
from srp.gestion_potreros.application.use_cases.registrar_potrero_manual import (
    RegistrarPotreroManual,
)
from srp.gestion_potreros.domain.entities import Potrero
from srp.gestion_potreros.domain.events import PotreroLevantado
from srp.gestion_potreros.domain.ports.potrero_repository import PotreroRepository
from srp.shared.events import DomainEvent
from srp.shared.ports import GeometriaValidator, PublicadorEventos
from srp.shared.types import FincaId, PotreroId

# ---- fakes ----


class RepoEnMemoria(PotreroRepository):
    def __init__(self) -> None:
        self.potreros: dict[PotreroId, Potrero] = {}

    async def guardar(self, potrero: Potrero) -> None:
        self.potreros[potrero.id] = potrero

    async def obtener(self, id: PotreroId) -> Potrero | None:
        return self.potreros.get(id)

    async def listar_por_finca(self, finca_id: FincaId) -> list[Potrero]:
        return [p for p in self.potreros.values() if p.finca_id == finca_id]


class ValidadorFake(GeometriaValidator):
    """Cumple el contrato del puerto con valores canjeados, sin geometría real."""

    def __init__(self, area_ha: float = 12.5, advertencia: str | None = None) -> None:
        self.area_ha = area_ha
        self.advertencia = advertencia
        self.llamadas: list[list[tuple[float, float]]] = []

    def construir_y_validar(self, puntos: list[tuple[float, float]]) -> dict:
        self.llamadas.append(puntos)
        anillo = [[lng, lat] for lat, lng in puntos] + [[puntos[0][1], puntos[0][0]]]
        return {
            "geojson": {"type": "Polygon", "coordinates": [anillo]},
            "area_ha": self.area_ha,
            "n_puntos": len(puntos),
            "advertencia": self.advertencia,
        }


class BusEspia(PublicadorEventos):
    def __init__(self) -> None:
        self.publicados: list[DomainEvent] = []

    async def publicar(self, eventos: list[DomainEvent]) -> None:
        self.publicados.extend(eventos)


PUNTOS = ((5.337, -72.396), (5.341, -72.396), (5.341, -72.392), (5.337, -72.392))


def _cmd_manual(finca_id: FincaId | None = None, **kwargs) -> RegistrarPotreroManualCommand:
    defaults = dict(
        finca_id=finca_id or FincaId(uuid.uuid4()),
        nombre="Potrero Norte",
        puntos=PUNTOS,
        especie_pasto_id=uuid.uuid4(),
        metodo_levantamiento="gps_app",
        tipo_suelo="franco-arcilloso",
        fuente_agua=True,
        accuracy_m=5.0,
    )
    defaults.update(kwargs)
    return RegistrarPotreroManualCommand(**defaults)


# ---- RegistrarPotreroManual ----


async def test_registrar_manual_guarda_y_publica_potrero_levantado():
    repo, validador, bus = RepoEnMemoria(), ValidadorFake(area_ha=19.6), BusEspia()
    dto = await RegistrarPotreroManual(repo, validador, bus).ejecutar(_cmd_manual())

    assert dto.area_ha == 19.6
    assert dto.estado == "descanso"
    assert dto.metodo_levantamiento == "gps_app"
    assert validador.llamadas == [list(PUNTOS)]

    guardado = repo.potreros[dto.id]
    assert guardado.nombre == "Potrero Norte"
    assert guardado.fuente_agua is True
    # eventos publicados en el bus y limpiados del agregado
    assert len(bus.publicados) == 1
    assert isinstance(bus.publicados[0], PotreroLevantado)
    assert bus.publicados[0].potrero_id == dto.id
    assert guardado.eventos_pendientes() == []


async def test_registrar_manual_propaga_advertencia_del_validador():
    repo, bus = RepoEnMemoria(), BusEspia()
    validador = ValidadorFake(advertencia="Área implausible")
    dto = await RegistrarPotreroManual(repo, validador, bus).ejecutar(_cmd_manual())
    assert dto.advertencia == "Área implausible"


# ---- ImportarPlanimetria ----


def _geojson_cuadrado() -> dict:
    anillo = [[lng, lat] for lat, lng in PUNTOS] + [[PUNTOS[0][1], PUNTOS[0][0]]]
    return {"type": "Polygon", "coordinates": [anillo]}


async def test_importar_planimetria_desde_geojson():
    repo, validador, bus = RepoEnMemoria(), ValidadorFake(area_ha=19.6), BusEspia()
    cmd = ImportarPlanimetriaCommand(
        finca_id=FincaId(uuid.uuid4()),
        nombre="Importado DXF",
        geojson=_geojson_cuadrado(),
        especie_pasto_id=uuid.uuid4(),
        metodo_levantamiento="dxf",
    )
    dto = await ImportarPlanimetria(repo, validador, bus).ejecutar(cmd)

    assert dto.metodo_levantamiento == "dxf"
    # el validador recibió los puntos (lat, lng) sin el cierre del anillo
    assert validador.llamadas == [list(PUNTOS)]
    assert len(bus.publicados) == 1


async def test_importar_planimetria_acepta_feature():
    feature = {"type": "Feature", "properties": {}, "geometry": _geojson_cuadrado()}
    assert puntos_desde_geojson(feature) == [tuple(p) for p in PUNTOS]


async def test_importar_planimetria_rechaza_geojson_no_polygon():
    with pytest.raises(ValueError):
        puntos_desde_geojson({"type": "Point", "coordinates": [-72.396, 5.337]})


# ---- Listar / Obtener ----


async def test_listar_potreros_filtra_por_finca():
    repo, validador, bus = RepoEnMemoria(), ValidadorFake(), BusEspia()
    caso = RegistrarPotreroManual(repo, validador, bus)
    finca_a, finca_b = FincaId(uuid.uuid4()), FincaId(uuid.uuid4())
    await caso.ejecutar(_cmd_manual(finca_id=finca_a, nombre="A1"))
    await caso.ejecutar(_cmd_manual(finca_id=finca_a, nombre="A2"))
    await caso.ejecutar(_cmd_manual(finca_id=finca_b, nombre="B1"))

    dtos = await ListarPotreros(repo).ejecutar(finca_a)
    assert sorted(d.nombre for d in dtos) == ["A1", "A2"]


async def test_obtener_potrero_inexistente_devuelve_none():
    repo = RepoEnMemoria()
    assert await ObtenerPotrero(repo).ejecutar(PotreroId(uuid.uuid4())) is None
