"""Fixtures de la unidad NDVI: potrero de prueba con geometría real en PostGIS."""

from __future__ import annotations

import json
import uuid

import pytest

# Polígono de ~1.1 km de lado cerca de Yopal, Casanare (WGS84).
WKT_POTRERO = (
    "SRID=4326;POLYGON(("
    "-72.40 5.33,-72.39 5.33,-72.39 5.34,-72.40 5.34,-72.40 5.33))"
)


@pytest.fixture
async def potrero(pool, organizacion):
    """Potrero persistido con geom real; devuelve su UUID."""
    _org_id, finca_id = organizacion
    especie_id = await pool.fetchval("SELECT id FROM especies_pasto LIMIT 1")
    assert especie_id is not None, "especies_pasto sin seed (migración 0001)"
    potrero_id = uuid.uuid4()
    await pool.execute(
        """
        INSERT INTO potreros
          (id, finca_id, nombre, geom, especie_pasto_id, metodo_levantamiento)
        VALUES ($1, $2, 'Potrero NDVI Test', ST_GeogFromText($3), $4, 'gps')
        """,
        potrero_id,
        finca_id,
        WKT_POTRERO,
        especie_id,
    )
    yield potrero_id
    await pool.execute("DELETE FROM lecturas_ndvi WHERE potrero_id = $1", potrero_id)
    await pool.execute("DELETE FROM potreros WHERE id = $1", potrero_id)


@pytest.fixture
async def poligono_geojson(pool, potrero) -> dict:
    """GeoJSON del potrero tal como lo produce el job (ST_AsGeoJSON)."""
    crudo = await pool.fetchval(
        "SELECT ST_AsGeoJSON(geom::geometry) FROM potreros WHERE id = $1", potrero
    )
    return json.loads(crudo)
