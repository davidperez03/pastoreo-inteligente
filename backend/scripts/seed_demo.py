"""Siembra datos de demo para probar el sistema end-to-end (mapa + dashboard).

Uso: DATABASE_URL=... PYTHONPATH=src python scripts/seed_demo.py

Crea una organización/finca con 4 potreros en distintos estados, un lote de
ganado, y un historial sintético de eventos BiomasaRecalculada + lecturas NDVI
para que el gráfico de historial tenga algo real que mostrar. Es idempotente:
si la finca demo ya existe, la reutiliza (borra y recrea sus potreros/lotes).
Imprime el token de desarrollo y los IDs a pegar en el navegador.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, timedelta

import asyncpg

from srp.shared.auth import emitir_token_dev
from srp.shared.db import database_url

ORG_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
FINCA_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

# (nombre, estado, offset_lng, offset_lat, tipo_suelo, biomasa_base)
POTREROS = [
    ("La Ceiba", "ocupado", 0.000, 0.000, "franco", 900.0),
    ("El Samán", "descanso", 0.006, 0.000, "arcilloso", 1800.0),
    ("Mata de Monte", "listo", 0.000, 0.006, "franco", 2900.0),
    ("Caño Seco", "descanso", 0.006, 0.006, "arenoso", 1200.0),
]
LADO = 0.004  # ~440 m de lado ≈ 19-20 ha por potrero


def _cuadrado(lng0: float, lat0: float) -> str:
    lng1, lat1 = lng0 + LADO, lat0 + LADO
    return (
        f"POLYGON(({lng0} {lat0}, {lng1} {lat0}, {lng1} {lat1}, "
        f"{lng0} {lat1}, {lng0} {lat0}))"
    )


async def main() -> None:
    pool = await asyncpg.create_pool(database_url())
    try:
        await pool.execute(
            "INSERT INTO organizaciones (id, nombre) VALUES ($1, 'Finca Demo SRP') "
            "ON CONFLICT (id) DO NOTHING",
            ORG_ID,
        )
        await pool.execute(
            "INSERT INTO fincas (id, organizacion_id, nombre) "
            "VALUES ($1, $2, 'La Esperanza') ON CONFLICT (id) DO NOTHING",
            FINCA_ID,
            ORG_ID,
        )
        # Reset de datos previos de la finca demo para que el script sea repetible.
        viejos = await pool.fetch(
            "SELECT id FROM potreros WHERE finca_id = $1", FINCA_ID
        )
        for fila in viejos:
            pid = fila["id"]
            await pool.execute("DELETE FROM lecturas_ndvi WHERE potrero_id = $1", pid)
            await pool.execute(
                "DELETE FROM eventos_pastoreo WHERE potrero_id = $1", pid
            )
            await pool.execute(
                "DELETE FROM eventos_dominio WHERE payload->>'potrero_id' = $1",
                str(pid),
            )
        await pool.execute("DELETE FROM lotes_ganado WHERE finca_id = $1", FINCA_ID)
        await pool.execute("DELETE FROM potreros WHERE finca_id = $1", FINCA_ID)

        especie_id = await pool.fetchval("SELECT id FROM especies_pasto LIMIT 1")
        base_lng, base_lat = -72.40, 5.33
        potrero_ids: dict[str, uuid.UUID] = {}

        for nombre, estado, dlng, dlat, suelo, biomasa in POTREROS:
            pid = uuid.uuid4()
            potrero_ids[nombre] = pid
            geom = _cuadrado(base_lng + dlng, base_lat + dlat)
            await pool.execute(
                f"""
                INSERT INTO potreros
                  (id, finca_id, nombre, geom, especie_pasto_id, tipo_suelo,
                   estado, fuente_agua, biomasa_actual_kg_ms_ha,
                   metodo_levantamiento, accuracy_m,
                   fecha_ultima_salida)
                VALUES ($1, $2, $3, ST_GeogFromText('{geom}'), $4, $5, $6, $7,
                        $8, 'digitalizacion', 5, $9)
                """,
                pid,
                FINCA_ID,
                nombre,
                especie_id,
                suelo,
                estado,
                nombre in ("El Samán", "Mata de Monte"),
                biomasa,
                date.today() - timedelta(days=10),
            )
            # Historial sintético de 20 días: crecimiento + un par de lecturas NDVI.
            for i in range(20, 0, -1):
                fecha = date.today() - timedelta(days=i)
                biomasa_i = round(biomasa - i * 15, 1)
                await pool.execute(
                    "INSERT INTO eventos_dominio (tipo, payload) VALUES "
                    "('BiomasaRecalculada', $1)",
                    json.dumps(
                        {
                            "potrero_id": str(pid),
                            "fecha": fecha.isoformat(),
                            "biomasa_kg_ms_ha": biomasa_i,
                            "fuente": "modelo",
                        }
                    ),
                )
                if i % 5 == 0:
                    ndvi = round(0.3 + (biomasa_i / 4500) * 0.5, 3)
                    await pool.execute(
                        "INSERT INTO lecturas_ndvi "
                        "(potrero_id, fecha, ndvi_promedio, cobertura_nubes_pct, stale) "
                        "VALUES ($1, $2, $3, 12, false)",
                        pid,
                        fecha,
                        ndvi,
                    )

        lote_id = uuid.uuid4()
        await pool.execute(
            "INSERT INTO lotes_ganado "
            "(id, finca_id, nombre, n_animales, peso_promedio_kg, potrero_actual_id) "
            "VALUES ($1, $2, 'Lote Ceba 1', 42, 420, $3)",
            lote_id,
            FINCA_ID,
            potrero_ids["La Ceiba"],
        )
        await pool.execute(
            "INSERT INTO eventos_pastoreo (lote_id, potrero_id, fecha_entrada) "
            "VALUES ($1, $2, $3)",
            lote_id,
            potrero_ids["La Ceiba"],
            date.today() - timedelta(days=3),
        )

        token = emitir_token_dev("demo-user", ORG_ID, "admin")

        print("Datos de demo creados.\n")
        print(f"organizacion_id = {ORG_ID}")
        print(f"finca_id        = {FINCA_ID}")
        print("potreros:")
        for nombre, pid in potrero_ids.items():
            print(f"  {nombre:15s} {pid}")
        print(f"\ntoken (dev, no usar en producción):\n{token}\n")
        print("En la consola del navegador (F12), en la página del frontend:")
        print(f'  sessionStorage.setItem("srp_token", "{token}");')
        print("  location.reload();")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
