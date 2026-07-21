"""Tests puros de dominio: sin base de datos, sin FastAPI, sin fixtures IO."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import date

import pytest

from srp.gestion_potreros.domain.entities import Potrero
from srp.gestion_potreros.domain.events import LoteSalioDePotrero, PotreroLevantado
from srp.gestion_potreros.domain.excepciones import DomainError
from srp.gestion_potreros.domain.value_objects import EstadoPotrero, FactorFatiga, Geometria
from srp.shared.types import Coordenada, FincaId, LoteId, PotreroId

# ---- helpers ----

_PUNTOS_CUADRADO = (
    Coordenada(5.337, -72.396),
    Coordenada(5.341, -72.396),
    Coordenada(5.341, -72.392),
    Coordenada(5.337, -72.392),
)


def _geometria(metodo: str = "gps_app") -> Geometria:
    return Geometria(puntos=_PUNTOS_CUADRADO, metodo_levantamiento=metodo, accuracy_m=4.0)


def _geojson() -> dict:
    anillo = [[c.lng, c.lat] for c in _PUNTOS_CUADRADO]
    anillo.append(anillo[0])
    return {"type": "Polygon", "coordinates": [anillo]}


def _potrero_nuevo(**kwargs) -> Potrero:
    defaults = dict(
        finca_id=FincaId(uuid.uuid4()),
        nombre="La Esperanza 1",
        geometria=_geometria(),
        geojson=_geojson(),
        area_ha=19.6,
        especie_pasto_id=uuid.uuid4(),
    )
    defaults.update(kwargs)
    return Potrero.crear(**defaults)


# ---- FactorFatiga ----


def test_factor_fatiga_neutro_es_uno():
    assert FactorFatiga.neutro().valor == 1.0


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [(0.2, 0.5), (0.5, 0.5), (0.9, 0.9), (1.3, 1.3), (2.7, 1.3), (-1.0, 0.5)],
)
def test_factor_fatiga_clamp_a_rango_valido(entrada: float, esperado: float):
    assert FactorFatiga(entrada).valor == esperado


def test_factor_fatiga_es_inmutable():
    ff = FactorFatiga.neutro()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ff.valor = 0.7  # type: ignore[misc]


# ---- Geometria ----


def test_geometria_requiere_tres_puntos():
    with pytest.raises(DomainError):
        Geometria(
            puntos=(Coordenada(5.3, -72.4), Coordenada(5.4, -72.4)),
            metodo_levantamiento="gps_app",
        )


def test_geometria_requiere_metodo_levantamiento():
    with pytest.raises(DomainError):
        Geometria(puntos=_PUNTOS_CUADRADO, metodo_levantamiento="")


def test_geometria_es_inmutable():
    geo = _geometria()
    with pytest.raises(dataclasses.FrozenInstanceError):
        geo.accuracy_m = 1.0  # type: ignore[misc]


# ---- Potrero: creación ----


def test_crear_potrero_emite_potrero_levantado():
    potrero = _potrero_nuevo()
    eventos = potrero.eventos_pendientes()
    assert len(eventos) == 1
    evento = eventos[0]
    assert isinstance(evento, PotreroLevantado)
    assert evento.potrero_id == potrero.id
    assert evento.area_ha == pytest.approx(19.6)
    assert evento.metodo == "gps_app"


def test_potrero_nuevo_arranca_en_descanso_con_fatiga_neutra():
    potrero = _potrero_nuevo()
    assert potrero.estado is EstadoPotrero.DESCANSO
    assert potrero.factor_fatiga == FactorFatiga.neutro()
    assert potrero.fecha_ultima_salida is None


def test_crear_potrero_valida_nombre_y_area():
    with pytest.raises(DomainError):
        _potrero_nuevo(nombre="   ")
    with pytest.raises(DomainError):
        _potrero_nuevo(area_ha=0)


def test_reconstituir_no_emite_eventos():
    potrero = Potrero.reconstituir(
        id=PotreroId(uuid.uuid4()),
        finca_id=FincaId(uuid.uuid4()),
        nombre="P1",
        geometria=_geometria(),
        geojson=_geojson(),
        area_ha=19.6,
        especie_pasto_id=uuid.uuid4(),
        tipo_suelo=None,
        fuente_agua=True,
        factor_fatiga=FactorFatiga(0.8),
        estado=EstadoPotrero.LISTO,
        fecha_ultima_salida=date(2026, 6, 1),
        biomasa_actual_kg_ms_ha=2100.0,
    )
    assert potrero.eventos_pendientes() == []
    assert potrero.estado is EstadoPotrero.LISTO


# ---- Potrero: transiciones de estado ----


def test_entrada_de_lote_pasa_a_ocupado():
    potrero = _potrero_nuevo()
    potrero.registrar_entrada_lote()
    assert potrero.estado is EstadoPotrero.OCUPADO


def test_entrada_sobre_potrero_ocupado_es_domain_error():
    potrero = _potrero_nuevo()
    potrero.registrar_entrada_lote()
    with pytest.raises(DomainError):
        potrero.registrar_entrada_lote()


def test_salida_sin_ocupacion_es_domain_error():
    potrero = _potrero_nuevo()
    with pytest.raises(DomainError):
        potrero.registrar_salida_lote(biomasa_final=1500.0)


def test_salida_pasa_a_descanso_y_emite_evento_con_firma_de_integracion():
    potrero = _potrero_nuevo()
    potrero.limpiar_eventos()
    lote_id = LoteId(uuid.uuid4())
    potrero.registrar_entrada_lote(
        lote_id=lote_id, fecha=date(2026, 7, 1), biomasa_inicial=2800.0
    )
    potrero.registrar_salida_lote(biomasa_final=1450.0, fecha=date(2026, 7, 4))

    assert potrero.estado is EstadoPotrero.DESCANSO
    assert potrero.fecha_ultima_salida == date(2026, 7, 4)
    assert potrero.biomasa_actual_kg_ms_ha == 1450.0

    eventos = potrero.eventos_pendientes()
    assert len(eventos) == 1
    evento = eventos[0]
    assert isinstance(evento, LoteSalioDePotrero)
    # Firma exacta del contrato de integración (§17.3): otro contexto la consume
    assert evento.potrero_id == potrero.id
    assert evento.lote_id == lote_id
    assert evento.fecha == date(2026, 7, 4)
    assert evento.biomasa_inicial == 2800.0
    assert evento.biomasa_final == 1450.0


def test_ciclo_completo_entrada_salida_entrada():
    potrero = _potrero_nuevo()
    potrero.registrar_entrada_lote()
    potrero.registrar_salida_lote(biomasa_final=1600.0)
    potrero.registrar_entrada_lote()  # tras descanso puede volver a ocuparse
    assert potrero.estado is EstadoPotrero.OCUPADO


def test_limpiar_eventos_vacia_pendientes():
    potrero = _potrero_nuevo()
    assert potrero.eventos_pendientes()
    potrero.limpiar_eventos()
    assert potrero.eventos_pendientes() == []
