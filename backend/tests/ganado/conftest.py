"""Fixtures del contexto Gestión de Ganado.

`potrero` inserta un potrero real (el contexto de ganado no escribe sobre
`potreros`, pero los FKs de `eventos_pastoreo` y `potrero_actual_id` lo
necesitan) y limpia lotes/eventos de la finca al terminar, antes de que la
fixture `organizacion` borre la finca.
"""

from __future__ import annotations

import uuid

import pytest

_GEOM_WKT = (
    "POLYGON((-72.396 5.337, -72.392 5.337, -72.392 5.341, "
    "-72.396 5.341, -72.396 5.337))"
)


@pytest.fixture
async def potrero(pool, organizacion):
    """Crea un potrero de prueba en la finca y devuelve su id."""
    _org_id, finca_id = organizacion
    potrero_id = uuid.uuid4()
    await pool.execute(
        f"""
        INSERT INTO potreros (id, finca_id, nombre, geom, especie_pasto_id,
                              metodo_levantamiento)
        VALUES ($1, $2, $3, ST_GeogFromText('{_GEOM_WKT}'),
                (SELECT id FROM especies_pasto ORDER BY nombre LIMIT 1), 'test')
        """,
        potrero_id,
        finca_id,
        f"Potrero U6 {potrero_id.hex[:8]}",
    )
    yield potrero_id
    await pool.execute(
        "DELETE FROM eventos_pastoreo WHERE potrero_id = $1", potrero_id
    )
    await pool.execute("DELETE FROM lotes_ganado WHERE finca_id = $1", finca_id)
    await pool.execute("DELETE FROM potreros WHERE id = $1", potrero_id)
