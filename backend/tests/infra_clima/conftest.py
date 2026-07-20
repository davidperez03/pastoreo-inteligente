"""Fixtures de la unidad de infraestructura de clima."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def respuesta_open_meteo() -> dict:
    """Respuesta real (grabada) de /v1/forecast con bloque daily."""
    return json.loads((FIXTURES_DIR / "open_meteo_daily.json").read_text())


@pytest.fixture
async def estacion(pool):
    """Estación de clima de prueba en Yopal, Casanare. Devuelve su id."""
    estacion_id = uuid.uuid4()
    await pool.execute(
        """
        INSERT INTO estaciones_clima (id, nombre, ubicacion, fuente)
        VALUES ($1, 'Estación Test Yopal',
                ST_GeogFromText('SRID=4326;POINT(-72.3959 5.3378)'), 'open-meteo')
        """,
        estacion_id,
    )
    yield estacion_id
    await pool.execute(
        "DELETE FROM registros_clima WHERE estacion_clima_id = $1", estacion_id
    )
    await pool.execute("DELETE FROM estaciones_clima WHERE id = $1", estacion_id)
