"""Tests de la proyección de historial contra Postgres real."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest

from srp.consultas.historial_potrero import PotreroNoVisible, historial_potrero

HOY = date.today()
GEOM = (
    "POLYGON((-72.396 5.337, -72.392 5.337, -72.392 5.341, "
    "-72.396 5.341, -72.396 5.337))"
)


@pytest.fixture
async def potrero(pool, organizacion):
    org_id, finca_id = organizacion
    potrero_id = uuid.uuid4()
    await pool.execute(
        f"""
        INSERT INTO potreros (id, finca_id, nombre, geom, especie_pasto_id,
                              metodo_levantamiento)
        SELECT $1, $2, 'Historial-P1', ST_GeogFromText('{GEOM}'), id, 'test'
        FROM especies_pasto LIMIT 1
        """,
        potrero_id,
        finca_id,
    )
    yield org_id, potrero_id
    await pool.execute("DELETE FROM lecturas_ndvi WHERE potrero_id = $1", potrero_id)
    await pool.execute("DELETE FROM eventos_pastoreo WHERE potrero_id = $1", potrero_id)
    await pool.execute(
        "DELETE FROM eventos_dominio WHERE payload->>'potrero_id' = $1",
        str(potrero_id),
    )
    await pool.execute("DELETE FROM potreros WHERE id = $1", potrero_id)


async def _evento_biomasa(pool, potrero_id, fecha, biomasa, fuente):
    await pool.execute(
        "INSERT INTO eventos_dominio (tipo, payload) VALUES ('BiomasaRecalculada', $1)",
        json.dumps(
            {
                "potrero_id": str(potrero_id),
                "fecha": fecha.isoformat(),
                "biomasa_kg_ms_ha": biomasa,
                "fuente": fuente,
            }
        ),
    )


async def test_combina_modelo_ndvi_y_eventos(pool, potrero):
    org_id, potrero_id = potrero
    d1, d2 = HOY - timedelta(days=3), HOY - timedelta(days=2)
    await _evento_biomasa(pool, potrero_id, d1, 1500.0, "modelo")
    await _evento_biomasa(pool, potrero_id, d2, 1540.0, "modelo")
    await pool.execute(
        """
        INSERT INTO lecturas_ndvi (potrero_id, fecha, ndvi_promedio, stale)
        VALUES ($1, $2, 0.55, false)
        """,
        potrero_id,
        d2,
    )
    # Lote real: entrada d1, salida d2.
    lote_id = uuid.uuid4()
    await pool.execute(
        """
        INSERT INTO lotes_ganado (id, finca_id, n_animales, peso_promedio_kg)
        SELECT $1, finca_id, 10, 400 FROM potreros WHERE id = $2
        """,
        lote_id,
        potrero_id,
    )
    await pool.execute(
        """
        INSERT INTO eventos_pastoreo (lote_id, potrero_id, fecha_entrada, fecha_salida)
        VALUES ($1, $2, $3, $4)
        """,
        lote_id,
        potrero_id,
        d1,
        d2,
    )

    puntos = await historial_potrero(pool, org_id, potrero_id)

    try:
        por_fecha = {p.fecha: p for p in puntos}
        assert por_fecha[d1].biomasa_modelo == 1500.0
        assert por_fecha[d1].evento == "entrada"
        assert por_fecha[d2].biomasa_modelo == 1540.0
        assert por_fecha[d2].evento == "salida"
        # NDVI 0.55 → interpolación lineal [0.2,0.9]→[300,4500] = 2400
        assert por_fecha[d2].biomasa_ndvi == 2400.0
        assert [p.fecha for p in puntos] == sorted(por_fecha)
    finally:
        await pool.execute(
            "DELETE FROM eventos_pastoreo WHERE lote_id = $1", lote_id
        )
        await pool.execute("DELETE FROM lotes_ganado WHERE id = $1", lote_id)


async def test_correccion_kalman_prevalece_sobre_modelo(pool, potrero):
    org_id, potrero_id = potrero
    d = HOY - timedelta(days=1)
    await _evento_biomasa(pool, potrero_id, d, 1500.0, "modelo")
    await _evento_biomasa(pool, potrero_id, d, 1720.0, "kalman")

    puntos = await historial_potrero(pool, org_id, potrero_id)
    assert puntos[-1].biomasa_modelo == 1720.0


async def test_ndvi_stale_no_aparece(pool, potrero):
    org_id, potrero_id = potrero
    await pool.execute(
        """
        INSERT INTO lecturas_ndvi (potrero_id, fecha, ndvi_promedio, stale)
        VALUES ($1, $2, 0.7, true)
        """,
        potrero_id,
        HOY - timedelta(days=1),
    )
    puntos = await historial_potrero(pool, org_id, potrero_id)
    assert all(p.biomasa_ndvi is None for p in puntos)


async def test_ventana_de_dias_filtra(pool, potrero):
    org_id, potrero_id = potrero
    await _evento_biomasa(pool, potrero_id, HOY - timedelta(days=40), 1100.0, "modelo")
    await _evento_biomasa(pool, potrero_id, HOY - timedelta(days=2), 1300.0, "modelo")

    puntos = await historial_potrero(pool, org_id, potrero_id, dias=7)
    assert len(puntos) == 1 and puntos[0].biomasa_modelo == 1300.0


async def test_potrero_de_otra_organizacion_no_visible(pool, potrero):
    _, potrero_id = potrero
    otra_org = uuid.uuid4()
    await pool.execute(
        "INSERT INTO organizaciones (id, nombre) VALUES ($1, 'Otra Org')", otra_org
    )
    try:
        with pytest.raises(PotreroNoVisible):
            await historial_potrero(pool, otra_org, potrero_id)
    finally:
        await pool.execute("DELETE FROM organizaciones WHERE id = $1", otra_org)
