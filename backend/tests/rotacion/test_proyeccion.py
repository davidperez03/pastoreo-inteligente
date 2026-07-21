"""Test de la proyección de lectura contra Postgres real (fixtures pool +
organizacion de tests/conftest.py; requiere migraciones aplicadas)."""

from __future__ import annotations

import uuid
from datetime import date

from srp.rotacion.infrastructure.proyeccion_postgres import ProyeccionRotacionPostgres

# Polígonos pequeños cerca de Yopal, Casanare (lng -72.39, lat 5.33).
GEOM_1 = (
    "POLYGON((-72.3900 5.3300, -72.3890 5.3300, -72.3890 5.3310, "
    "-72.3900 5.3310, -72.3900 5.3300))"
)


async def _insertar_potrero(pool, finca_id, nombre, biomasa, **kw):
    especie = await pool.fetchrow(
        "SELECT id, dias_descanso_ideal FROM especies_pasto "
        "WHERE nombre = 'Brachiaria decumbens'"
    )
    pid = uuid.uuid4()
    await pool.execute(
        """
        INSERT INTO potreros
          (id, finca_id, nombre, geom, especie_pasto_id, biomasa_actual_kg_ms_ha,
           factor_fatiga, estado, fecha_ultima_salida, fuente_agua, metodo_levantamiento)
        VALUES ($1, $2, $3, ST_GeogFromText($4), $5, $6, $7, $8, $9, $10, 'test')
        """,
        pid,
        finca_id,
        nombre,
        GEOM_1,
        especie["id"],
        biomasa,
        kw.get("factor_fatiga", 1.0),
        kw.get("estado", "descanso"),
        kw.get("fecha_ultima_salida"),
        kw.get("fuente_agua", False),
    )
    return pid, especie["dias_descanso_ideal"]


async def test_proyeccion_potreros_y_lotes(pool, organizacion):
    org_id, finca_id = organizacion
    potrero_id, dias_ideal = await _insertar_potrero(
        pool,
        finca_id,
        "Proyectado",
        3200.0,
        factor_fatiga=0.9,
        estado="listo",
        fecha_ultima_salida=date(2026, 6, 1),
        fuente_agua=True,
    )
    lote_id = uuid.uuid4()
    await pool.execute(
        """
        INSERT INTO lotes_ganado
          (id, finca_id, nombre, n_animales, peso_promedio_kg, potrero_actual_id)
        VALUES ($1, $2, 'Lote 1', 45, 450, $3)
        """,
        lote_id,
        finca_id,
        potrero_id,
    )
    try:
        proyeccion = ProyeccionRotacionPostgres(pool, org_id)

        potreros = await proyeccion.potreros_de_finca(finca_id)
        assert len(potreros) == 1
        p = potreros[0]
        assert p.id == potrero_id
        assert p.finca_id == finca_id
        assert p.nombre == "Proyectado"
        assert p.area_ha > 0  # calculado por trigger desde la geometría
        assert p.estado == "listo"
        assert p.biomasa_kg_ms_ha == 3200.0
        assert p.factor_fatiga == 0.9
        assert p.dias_descanso_ideal == dias_ideal  # JOIN con especies_pasto
        assert p.fecha_ultima_salida == date(2026, 6, 1)
        assert p.fuente_agua is True

        lotes = await proyeccion.lotes_de_finca(finca_id)
        assert len(lotes) == 1
        lo = lotes[0]
        assert lo.id == lote_id
        assert lo.n_animales == 45
        assert lo.ua_equivalente == 45.0  # 45 * 450 / 450 (columna generada)
        assert lo.potrero_actual_id == potrero_id

        # Nota: no se afirma aislamiento RLS aquí porque el rol de tests es
        # owner de las tablas y bypassa RLS (ver nota en la migración 0001).
    finally:
        await pool.execute("DELETE FROM lotes_ganado WHERE id = $1", lote_id)
        await pool.execute("DELETE FROM potreros WHERE id = $1", potrero_id)
