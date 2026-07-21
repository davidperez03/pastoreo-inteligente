"""Agregado `Potrero` (§17.2).

Raíz de agregado del contexto Gestión de Potreros: encapsula las transiciones
de estado del ciclo de pastoreo y emite eventos de dominio. Sin dependencias
de infraestructura (§18.4).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from srp.gestion_potreros.domain.events import LoteSalioDePotrero, PotreroLevantado
from srp.gestion_potreros.domain.excepciones import DomainError
from srp.gestion_potreros.domain.value_objects import EstadoPotrero, FactorFatiga, Geometria
from srp.shared.events import DomainEvent
from srp.shared.types import FincaId, LoteId, PotreroId


@dataclass(frozen=True)
class _Ocupacion:
    """Estado interno de la ocupación en curso (para el evento de salida)."""

    lote_id: LoteId | None
    fecha_entrada: date
    biomasa_inicial: float | None


class Potrero:
    """Aggregate root. Se construye con `crear(...)` (potrero nuevo, emite
    `PotreroLevantado`) o `reconstituir(...)` (rehidratación desde
    persistencia, sin eventos)."""

    def __init__(
        self,
        id: PotreroId,
        finca_id: FincaId,
        nombre: str,
        geometria: Geometria,
        geojson: dict,
        area_ha: float,
        especie_pasto_id: uuid.UUID,
        tipo_suelo: str | None = None,
        fuente_agua: bool = False,
        factor_fatiga: FactorFatiga | None = None,
        estado: EstadoPotrero = EstadoPotrero.DESCANSO,
        fecha_ultima_salida: date | None = None,
        biomasa_actual_kg_ms_ha: float | None = None,
    ) -> None:
        if not nombre or not nombre.strip():
            raise DomainError("El potrero requiere un nombre")
        if area_ha <= 0:
            raise DomainError("El área del potrero debe ser positiva")
        self._id = id
        self._finca_id = finca_id
        self._nombre = nombre.strip()
        self._geometria = geometria
        self._geojson = geojson
        self._area_ha = area_ha
        self._especie_pasto_id = especie_pasto_id
        self._tipo_suelo = tipo_suelo
        self._fuente_agua = fuente_agua
        self._factor_fatiga = factor_fatiga or FactorFatiga.neutro()
        self._estado = estado
        self._fecha_ultima_salida = fecha_ultima_salida
        self._biomasa_actual_kg_ms_ha = biomasa_actual_kg_ms_ha
        self._ocupacion: _Ocupacion | None = None
        self._eventos: list[DomainEvent] = []

    # ---- fábricas ----

    @classmethod
    def crear(
        cls,
        finca_id: FincaId,
        nombre: str,
        geometria: Geometria,
        geojson: dict,
        area_ha: float,
        especie_pasto_id: uuid.UUID,
        tipo_suelo: str | None = None,
        fuente_agua: bool = False,
        id: PotreroId | None = None,
    ) -> Potrero:
        """Levanta un potrero nuevo y emite `PotreroLevantado`."""
        potrero = cls(
            id=id or PotreroId(uuid.uuid4()),
            finca_id=finca_id,
            nombre=nombre,
            geometria=geometria,
            geojson=geojson,
            area_ha=area_ha,
            especie_pasto_id=especie_pasto_id,
            tipo_suelo=tipo_suelo,
            fuente_agua=fuente_agua,
        )
        potrero._eventos.append(
            PotreroLevantado(
                potrero_id=potrero._id,
                area_ha=potrero._area_ha,
                metodo=geometria.metodo_levantamiento,
            )
        )
        return potrero

    @classmethod
    def reconstituir(
        cls,
        id: PotreroId,
        finca_id: FincaId,
        nombre: str,
        geometria: Geometria,
        geojson: dict,
        area_ha: float,
        especie_pasto_id: uuid.UUID,
        tipo_suelo: str | None,
        fuente_agua: bool,
        factor_fatiga: FactorFatiga,
        estado: EstadoPotrero,
        fecha_ultima_salida: date | None,
        biomasa_actual_kg_ms_ha: float | None,
    ) -> Potrero:
        """Rehidrata el agregado desde persistencia — no emite eventos."""
        return cls(
            id=id,
            finca_id=finca_id,
            nombre=nombre,
            geometria=geometria,
            geojson=geojson,
            area_ha=area_ha,
            especie_pasto_id=especie_pasto_id,
            tipo_suelo=tipo_suelo,
            fuente_agua=fuente_agua,
            factor_fatiga=factor_fatiga,
            estado=estado,
            fecha_ultima_salida=fecha_ultima_salida,
            biomasa_actual_kg_ms_ha=biomasa_actual_kg_ms_ha,
        )

    # ---- comportamiento del ciclo de pastoreo ----

    def registrar_entrada_lote(
        self,
        lote_id: LoteId | None = None,
        fecha: date | None = None,
        biomasa_inicial: float | None = None,
    ) -> None:
        """Un lote entra a pastorear: el potrero pasa a OCUPADO."""
        if self._estado == EstadoPotrero.OCUPADO:
            raise DomainError(
                "No se puede registrar entrada: el potrero ya está ocupado"
            )
        self._estado = EstadoPotrero.OCUPADO
        self._ocupacion = _Ocupacion(
            lote_id=lote_id,
            fecha_entrada=fecha or date.today(),
            biomasa_inicial=biomasa_inicial,
        )

    def registrar_salida_lote(
        self, biomasa_final: float | None, fecha: date | None = None
    ) -> None:
        """El lote sale: valida OCUPADO, pasa a DESCANSO y emite
        `LoteSalioDePotrero` (contrato de integración, §17.3)."""
        if self._estado != EstadoPotrero.OCUPADO:
            raise DomainError(
                "No se puede registrar salida de un potrero no ocupado"
            )
        fecha_salida = fecha or date.today()
        self._estado = EstadoPotrero.DESCANSO
        self._fecha_ultima_salida = fecha_salida
        if biomasa_final is not None:
            self._biomasa_actual_kg_ms_ha = biomasa_final
        self._eventos.append(
            LoteSalioDePotrero(
                potrero_id=self._id,
                lote_id=self._ocupacion.lote_id if self._ocupacion else None,
                fecha=fecha_salida,
                biomasa_inicial=(
                    self._ocupacion.biomasa_inicial if self._ocupacion else None
                ),
                biomasa_final=biomasa_final,
            )
        )
        self._ocupacion = None

    # ---- eventos ----

    def eventos_pendientes(self) -> list[DomainEvent]:
        return list(self._eventos)

    def limpiar_eventos(self) -> None:
        self._eventos.clear()

    # ---- propiedades de solo lectura ----

    @property
    def id(self) -> PotreroId:
        return self._id

    @property
    def finca_id(self) -> FincaId:
        return self._finca_id

    @property
    def nombre(self) -> str:
        return self._nombre

    @property
    def geometria(self) -> Geometria:
        return self._geometria

    @property
    def geojson(self) -> dict:
        return self._geojson

    @property
    def area_ha(self) -> float:
        return self._area_ha

    @property
    def especie_pasto_id(self) -> uuid.UUID:
        return self._especie_pasto_id

    @property
    def tipo_suelo(self) -> str | None:
        return self._tipo_suelo

    @property
    def fuente_agua(self) -> bool:
        return self._fuente_agua

    @property
    def factor_fatiga(self) -> FactorFatiga:
        return self._factor_fatiga

    @property
    def estado(self) -> EstadoPotrero:
        return self._estado

    @property
    def fecha_ultima_salida(self) -> date | None:
        return self._fecha_ultima_salida

    @property
    def biomasa_actual_kg_ms_ha(self) -> float | None:
        return self._biomasa_actual_kg_ms_ha
