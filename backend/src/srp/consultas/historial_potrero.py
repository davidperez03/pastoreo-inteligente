"""Historial de un potrero: biomasa modelo vs NDVI vs eventos de pastoreo (§9).

La pieza de explicabilidad (§16): el ganadero ve en una sola serie lo que el
modelo predijo, lo que el satélite observó y lo que de verdad pasó en campo.

Fuentes (solo lectura):
- `eventos_dominio` — eventos `BiomasaRecalculada` del job diario (fuente
  "modelo"/"kalman"; el último del día prevalece, que es el corregido).
- `lecturas_ndvi` — lecturas frescas (no stale), convertidas a biomasa
  equivalente con el mismo mapeo que usa la corrección del Kalman.
- `eventos_pastoreo` — entradas/salidas reales de lotes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta

import asyncpg

from srp.agronomia.domain.crecimiento import ParametrosEspecie
from srp.agronomia.domain.ndvi_biomasa import biomasa_desde_ndvi
from srp.shared.db import conexion_org
from srp.shared.types import OrganizacionId, PotreroId

DIAS_DEFAULT = 90


@dataclass(frozen=True)
class PuntoHistorial:
    fecha: date
    biomasa_modelo: float | None
    biomasa_ndvi: float | None
    evento: str | None  # 'entrada' | 'salida' | None


class PotreroNoVisible(LookupError):
    """El potrero no existe o la RLS lo oculta para esta organización."""


async def historial_potrero(
    pool: asyncpg.Pool,
    org_id: OrganizacionId,
    potrero_id: PotreroId,
    dias: int = DIAS_DEFAULT,
) -> list[PuntoHistorial]:
    desde = date.today() - timedelta(days=dias)

    # Visibilidad: filtro explícito de organización ADEMÁS de la RLS (defensa
    # en profundidad — una conexión de rol owner bypassa la RLS). El resto de
    # lecturas quedan autorizadas por esta comprobación.
    async with conexion_org(pool, org_id) as con:
        potrero = await con.fetchrow(
            """
            SELECT p.id, e.nombre, e.temp_base, e.tasa_max_crecimiento,
                   e.gdd_optimo_diario, e.dias_descanso_ideal, e.curva_k
            FROM potreros p
            JOIN fincas f ON f.id = p.finca_id
            JOIN especies_pasto e ON e.id = p.especie_pasto_id
            WHERE p.id = $1 AND f.organizacion_id = $2
            """,
            potrero_id,
            org_id,
        )
    if potrero is None:
        raise PotreroNoVisible(str(potrero_id))
    especie = ParametrosEspecie(
        nombre=potrero["nombre"],
        temp_base=float(potrero["temp_base"]),
        tasa_max_crecimiento=float(potrero["tasa_max_crecimiento"]),
        gdd_optimo_diario=float(potrero["gdd_optimo_diario"]),
        dias_descanso_ideal=int(potrero["dias_descanso_ideal"]),
        curva_k=float(potrero["curva_k"]),
    )

    modelo = await _serie_modelo(pool, potrero_id, desde)
    ndvi = await _serie_ndvi(pool, potrero_id, desde, especie)
    eventos = await _eventos_pastoreo(pool, potrero_id, desde)

    fechas = sorted(set(modelo) | set(ndvi) | set(eventos))
    return [
        PuntoHistorial(
            fecha=f,
            biomasa_modelo=modelo.get(f),
            biomasa_ndvi=ndvi.get(f),
            evento=eventos.get(f),
        )
        for f in fechas
    ]


async def _serie_modelo(
    pool: asyncpg.Pool, potrero_id: PotreroId, desde: date
) -> dict[date, float]:
    filas = await pool.fetch(
        """
        SELECT payload FROM eventos_dominio
        WHERE tipo = 'BiomasaRecalculada' AND payload->>'potrero_id' = $1
          AND (payload->>'fecha')::date >= $2
        ORDER BY id
        """,
        str(potrero_id),
        desde,
    )
    serie: dict[date, float] = {}
    for fila in filas:
        payload = json.loads(fila["payload"])
        # El orden por id hace que el último evento del día (la corrección
        # kalman, si hubo) sobrescriba al de solo-modelo.
        serie[date.fromisoformat(payload["fecha"])] = round(
            float(payload["biomasa_kg_ms_ha"]), 1
        )
    return serie


async def _serie_ndvi(
    pool: asyncpg.Pool,
    potrero_id: PotreroId,
    desde: date,
    especie: ParametrosEspecie,
) -> dict[date, float]:
    filas = await pool.fetch(
        """
        SELECT fecha, ndvi_promedio FROM lecturas_ndvi
        WHERE potrero_id = $1 AND NOT stale AND ndvi_promedio IS NOT NULL
          AND fecha >= $2
        """,
        potrero_id,
        desde,
    )
    return {
        fila["fecha"]: round(
            biomasa_desde_ndvi(float(fila["ndvi_promedio"]), especie), 1
        )
        for fila in filas
    }


async def _eventos_pastoreo(
    pool: asyncpg.Pool, potrero_id: PotreroId, desde: date
) -> dict[date, str]:
    filas = await pool.fetch(
        """
        SELECT fecha_entrada, fecha_salida FROM eventos_pastoreo
        WHERE potrero_id = $1
          AND (fecha_entrada >= $2 OR fecha_salida >= $2)
        ORDER BY fecha_entrada
        """,
        potrero_id,
        desde,
    )
    eventos: dict[date, str] = {}
    for fila in filas:
        if fila["fecha_entrada"] and fila["fecha_entrada"] >= desde:
            eventos[fila["fecha_entrada"]] = "entrada"
        if fila["fecha_salida"] and fila["fecha_salida"] >= desde:
            # Mismo día entrada y salida: prevalece la salida (estado final).
            eventos[fila["fecha_salida"]] = "salida"
    return eventos
