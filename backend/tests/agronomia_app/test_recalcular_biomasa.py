"""Tests del job diario de biomasa contra Postgres real.

Requieren la DB de docker-compose con migraciones (make db-up && make migrate);
sin DB los tests se saltan (fixture `pool` de conftest).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from srp.agronomia.application.recalcular_biomasa import (
    BIOMASA_INICIAL_KG_MS_HA,
    recalcular_biomasa_diaria,
)
from srp.agronomia.domain.events import BiomasaRecalculada

AYER = date.today() - timedelta(days=1)
GEOM = (
    "POLYGON((-72.396 5.337, -72.392 5.337, -72.392 5.341, "
    "-72.396 5.341, -72.396 5.337))"
)


@pytest.fixture
async def potrero_con_clima(pool, organizacion):
    """Potrero con estación de clima asignada y registro climático de ayer."""
    _, finca_id = organizacion
    estacion_id = uuid.uuid4()
    await pool.execute(
        "INSERT INTO estaciones_clima (id, nombre) VALUES ($1, 'Estación Test')",
        estacion_id,
    )
    await pool.execute(
        "UPDATE fincas SET estacion_clima_id = $2 WHERE id = $1",
        finca_id,
        estacion_id,
    )
    await pool.execute(
        """
        INSERT INTO registros_clima
          (estacion_clima_id, fecha, temp_media, temp_max, temp_min, precipitacion_mm)
        VALUES ($1, $2, 27, 33, 22, 12)
        """,
        estacion_id,
        AYER,
    )
    potrero_id = uuid.uuid4()
    await pool.execute(
        f"""
        INSERT INTO potreros
          (id, finca_id, nombre, geom, especie_pasto_id, tipo_suelo,
           metodo_levantamiento)
        SELECT $1, $2, 'Biomasa-P1', ST_GeogFromText('{GEOM}'), id, 'franco', 'test'
        FROM especies_pasto LIMIT 1
        """,
        potrero_id,
        finca_id,
    )
    yield potrero_id, estacion_id
    await pool.execute("DELETE FROM lecturas_ndvi WHERE potrero_id = $1", potrero_id)
    await pool.execute("DELETE FROM potreros WHERE id = $1", potrero_id)
    await pool.execute(
        "UPDATE fincas SET estacion_clima_id = NULL WHERE id = $1", finca_id
    )
    await pool.execute(
        "DELETE FROM registros_clima WHERE estacion_clima_id = $1", estacion_id
    )
    await pool.execute("DELETE FROM estaciones_clima WHERE id = $1", estacion_id)
    await pool.execute(
        "DELETE FROM eventos_dominio WHERE payload->>'potrero_id' = $1",
        str(potrero_id),
    )


async def _estado(pool, potrero_id):
    return await pool.fetchrow(
        """
        SELECT biomasa_actual_kg_ms_ha, kalman_varianza, suelo_mm
        FROM potreros WHERE id = $1
        """,
        potrero_id,
    )


async def test_arranque_en_frio_inicializa_y_crece(pool, potrero_con_clima):
    potrero_id, _ = potrero_con_clima
    resultado = await recalcular_biomasa_diaria(pool, fecha=AYER)
    assert resultado["ok"] >= 1 and resultado["fallidos"] == 0

    estado = await _estado(pool, potrero_id)
    # Con 27°C y suelo a media capacidad, el crecimiento del día es positivo.
    assert float(estado["biomasa_actual_kg_ms_ha"]) > BIOMASA_INICIAL_KG_MS_HA
    assert estado["kalman_varianza"] is not None
    assert estado["suelo_mm"] is not None


async def test_estado_persiste_entre_corridas(pool, potrero_con_clima):
    potrero_id, _ = potrero_con_clima
    await recalcular_biomasa_diaria(pool, fecha=AYER)
    primera = await _estado(pool, potrero_id)
    await recalcular_biomasa_diaria(pool, fecha=AYER)
    segunda = await _estado(pool, potrero_id)
    # La segunda corrida parte del estado persistido (no reinicia a valores
    # de arranque): la biomasa sigue avanzando desde la primera.
    assert float(segunda["biomasa_actual_kg_ms_ha"]) > float(
        primera["biomasa_actual_kg_ms_ha"]
    )


async def test_correccion_ndvi_fresco_ajusta_hacia_observacion(
    pool, potrero_con_clima
):
    potrero_id, _ = potrero_con_clima
    # NDVI alto (0.8) implica biomasa observada muy por encima del arranque
    # en frío: la corrección debe subir la estimación más que el solo modelo.
    await pool.execute(
        """
        INSERT INTO lecturas_ndvi (potrero_id, fecha, ndvi_promedio,
                                   cobertura_nubes_pct, stale)
        VALUES ($1, $2, 0.8, 10, false)
        """,
        potrero_id,
        AYER,
    )
    await recalcular_biomasa_diaria(pool, fecha=AYER)
    con_ndvi = float((await _estado(pool, potrero_id))["biomasa_actual_kg_ms_ha"])
    # Solo-modelo desde el arranque: biomasa inicial + crecimiento de un día
    # (< 100 kg). Con la corrección NDVI debe quedar muy por encima.
    assert con_ndvi > BIOMASA_INICIAL_KG_MS_HA + 200


async def test_lectura_stale_no_corrige(pool, potrero_con_clima):
    potrero_id, _ = potrero_con_clima
    await pool.execute(
        """
        INSERT INTO lecturas_ndvi (potrero_id, fecha, ndvi_promedio,
                                   cobertura_nubes_pct, stale)
        VALUES ($1, $2, 0.8, 10, true)
        """,
        potrero_id,
        AYER,
    )
    await recalcular_biomasa_diaria(pool, fecha=AYER)
    biomasa = float((await _estado(pool, potrero_id))["biomasa_actual_kg_ms_ha"])
    # Sin corrección: solo el crecimiento del día sobre el arranque en frío.
    assert biomasa < BIOMASA_INICIAL_KG_MS_HA + 200


async def test_sin_clima_omite_sin_fallar(pool, potrero_con_clima):
    potrero_id, estacion_id = potrero_con_clima
    await pool.execute(
        "DELETE FROM registros_clima WHERE estacion_clima_id = $1", estacion_id
    )
    resultado = await recalcular_biomasa_diaria(pool, fecha=AYER)
    assert resultado["fallidos"] == 0 and resultado["sin_clima"] >= 1
    estado = await _estado(pool, potrero_id)
    assert estado["biomasa_actual_kg_ms_ha"] is None  # intacto


async def test_eventos_auditados_y_publicados(pool, potrero_con_clima, bus):
    potrero_id, _ = potrero_con_clima
    recibidos: list[BiomasaRecalculada] = []
    bus.suscribir(BiomasaRecalculada, recibidos.append)

    await recalcular_biomasa_diaria(pool, bus=bus, fecha=AYER)

    assert any(e.potrero_id == potrero_id for e in recibidos)
    fila = await pool.fetchrow(
        """
        SELECT payload FROM eventos_dominio
        WHERE tipo = 'BiomasaRecalculada' AND payload->>'potrero_id' = $1
        ORDER BY id DESC LIMIT 1
        """,
        str(potrero_id),
    )
    assert fila is not None
