"""Persistencia de lecturas NDVI (tabla lecturas_ndvi, §2, §11).

`guardar_lectura` es idempotente vía ON CONFLICT sobre UNIQUE(potrero_id,
fecha): el job semanal puede reejecutarse sin duplicar filas (§11).
"""

from __future__ import annotations

import uuid

import asyncpg

from srp.shared.types import LecturaNdvi


def _cobertura_desde_calidad(calidad: float) -> float:
    """calidad = 1 - cloudCover/100 → cobertura_nubes_pct = (1 - calidad) * 100."""
    return round((1.0 - calidad) * 100.0, 2)


async def guardar_lectura(
    pool: asyncpg.Pool,
    potrero_id: uuid.UUID,
    lectura: LecturaNdvi,
) -> None:
    """Inserta o actualiza la lectura del potrero para esa fecha (idempotente)."""
    await pool.execute(
        """
        INSERT INTO lecturas_ndvi
          (potrero_id, fecha, ndvi_promedio, cobertura_nubes_pct, stale, fuente)
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (potrero_id, fecha) DO UPDATE SET
          ndvi_promedio = EXCLUDED.ndvi_promedio,
          cobertura_nubes_pct = EXCLUDED.cobertura_nubes_pct,
          stale = EXCLUDED.stale,
          fuente = EXCLUDED.fuente
        """,
        potrero_id,
        lectura.fecha,
        lectura.ndvi_promedio,
        _cobertura_desde_calidad(lectura.calidad),
        lectura.stale,
        lectura.fuente,
    )


async def ultima_lectura(
    pool: asyncpg.Pool,
    potrero_id: uuid.UUID,
) -> LecturaNdvi | None:
    """Última lectura NDVI conocida del potrero (o None si nunca hubo)."""
    fila = await pool.fetchrow(
        """
        SELECT fecha, ndvi_promedio, cobertura_nubes_pct, stale, fuente
        FROM lecturas_ndvi
        WHERE potrero_id = $1
        ORDER BY fecha DESC
        LIMIT 1
        """,
        potrero_id,
    )
    if fila is None:
        return None
    cobertura = fila["cobertura_nubes_pct"]
    calidad = 1.0 if cobertura is None else 1.0 - float(cobertura) / 100.0
    return LecturaNdvi(
        fecha=fila["fecha"],
        ndvi_promedio=float(fila["ndvi_promedio"]),
        calidad=calidad,
        fuente=fila["fuente"],
        stale=fila["stale"],
    )
