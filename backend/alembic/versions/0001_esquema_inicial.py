"""Esquema inicial completo (§2 de la spec): PostGIS, RLS multi-tenant,
índices espaciales, constraints de integridad y seeds de especies.

Revision ID: 0001
Revises:
Create Date: 2026-07-20

"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE EXTENSION IF NOT EXISTS postgis;

    CREATE TABLE organizaciones (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      nombre TEXT NOT NULL,
      plan TEXT NOT NULL DEFAULT 'basico' CHECK (plan IN ('basico', 'pro', 'enterprise')),
      creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE estaciones_clima (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      nombre TEXT NOT NULL,
      ubicacion GEOGRAPHY(POINT, 4326),
      fuente TEXT NOT NULL DEFAULT 'open-meteo'
    );

    CREATE TABLE fincas (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      organizacion_id UUID NOT NULL REFERENCES organizaciones(id),
      nombre TEXT NOT NULL,
      ubicacion GEOGRAPHY(POINT, 4326),
      estacion_clima_id UUID REFERENCES estaciones_clima(id),
      creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX fincas_org_idx ON fincas (organizacion_id);

    CREATE TABLE especies_pasto (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      nombre TEXT UNIQUE NOT NULL,
      temp_optima_min NUMERIC,
      temp_optima_max NUMERIC,
      temp_base NUMERIC,
      tasa_max_crecimiento NUMERIC,          -- kg MS/ha/dia
      dias_descanso_ideal INT,
      curva_k NUMERIC,
      gdd_optimo_diario NUMERIC
    );

    CREATE TABLE potreros (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      finca_id UUID NOT NULL REFERENCES fincas(id),
      nombre TEXT NOT NULL,
      geom GEOGRAPHY(POLYGON, 4326) NOT NULL,
      area_ha NUMERIC,
      especie_pasto_id UUID NOT NULL REFERENCES especies_pasto(id),
      tipo_suelo TEXT,
      pendiente_pct NUMERIC,
      fuente_agua BOOLEAN NOT NULL DEFAULT false,
      factor_fatiga NUMERIC NOT NULL DEFAULT 1.0 CHECK (factor_fatiga BETWEEN 0.5 AND 1.3),
      n_ciclos_observados INT NOT NULL DEFAULT 0,
      estado TEXT NOT NULL DEFAULT 'descanso' CHECK (estado IN ('descanso', 'ocupado', 'listo')),
      fecha_ultima_salida DATE,
      biomasa_actual_kg_ms_ha NUMERIC,
      metodo_levantamiento TEXT NOT NULL,
      accuracy_m NUMERIC,
      creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
      actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (finca_id, nombre)
    );

    -- area_ha se mantiene por trigger y no como columna GENERATED: ST_Area
    -- sobre geography no es IMMUTABLE (usa parametros del esferoide), y
    -- Postgres rechaza funciones no inmutables en columnas generadas.
    CREATE FUNCTION potreros_actualizar_area() RETURNS trigger AS $$
    BEGIN
      NEW.area_ha := ST_Area(NEW.geom) / 10000;
      NEW.actualizado_en := now();
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER potreros_area_trg
      BEFORE INSERT OR UPDATE OF geom ON potreros
      FOR EACH ROW EXECUTE FUNCTION potreros_actualizar_area();

    CREATE INDEX potreros_geom_idx ON potreros USING GIST (geom);
    CREATE INDEX potreros_finca_idx ON potreros (finca_id);

    CREATE TABLE registros_clima (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      estacion_clima_id UUID NOT NULL REFERENCES estaciones_clima(id),
      fecha DATE NOT NULL,
      temp_media NUMERIC,
      temp_max NUMERIC,
      temp_min NUMERIC,
      precipitacion_mm NUMERIC,
      humedad_suelo_pct NUMERIC,
      estimado BOOLEAN NOT NULL DEFAULT false,
      UNIQUE (estacion_clima_id, fecha)
    );

    CREATE TABLE lotes_ganado (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      finca_id UUID NOT NULL REFERENCES fincas(id),
      nombre TEXT,
      n_animales INT NOT NULL CHECK (n_animales > 0),
      peso_promedio_kg NUMERIC NOT NULL CHECK (peso_promedio_kg > 0),
      ua_equivalente NUMERIC GENERATED ALWAYS AS (n_animales * peso_promedio_kg / 450) STORED,
      potrero_actual_id UUID REFERENCES potreros(id)
    );
    CREATE INDEX lotes_finca_idx ON lotes_ganado (finca_id);

    CREATE TABLE eventos_pastoreo (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      lote_id UUID NOT NULL REFERENCES lotes_ganado(id),
      potrero_id UUID NOT NULL REFERENCES potreros(id),
      fecha_entrada DATE NOT NULL,
      fecha_salida DATE,
      biomasa_inicial NUMERIC,
      biomasa_final NUMERIC,
      CHECK (fecha_salida IS NULL OR fecha_salida >= fecha_entrada)
    );
    CREATE INDEX eventos_potrero_idx ON eventos_pastoreo (potrero_id);

    CREATE TABLE lecturas_ndvi (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      potrero_id UUID NOT NULL REFERENCES potreros(id),
      fecha DATE NOT NULL,
      ndvi_promedio NUMERIC,
      cobertura_nubes_pct NUMERIC,
      stale BOOLEAN NOT NULL DEFAULT false,
      fuente TEXT NOT NULL DEFAULT 'sentinel-2',
      UNIQUE (potrero_id, fecha)
    );

    -- Auditoría/integración: persistencia de eventos de dominio (§10, §17.3)
    CREATE TABLE eventos_dominio (
      id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      tipo TEXT NOT NULL,
      payload JSONB NOT NULL,
      ocurrido_en TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    -- ---- Row Level Security multi-tenant (§2, §19) ----
    -- Nota: el owner de las tablas bypassa RLS salvo FORCE; en despliegue real
    -- la app se conecta con un rol NO owner. current_setting(..., true) evita
    -- error cuando el setting no existe: sin org fijada => cero filas.
    ALTER TABLE fincas ENABLE ROW LEVEL SECURITY;
    CREATE POLICY fincas_por_org ON fincas
      USING (organizacion_id = NULLIF(current_setting('app.current_org', true), '')::uuid);

    ALTER TABLE potreros ENABLE ROW LEVEL SECURITY;
    CREATE POLICY potreros_por_org ON potreros
      USING (finca_id IN (
        SELECT id FROM fincas
        WHERE organizacion_id = NULLIF(current_setting('app.current_org', true), '')::uuid
      ));

    ALTER TABLE lotes_ganado ENABLE ROW LEVEL SECURITY;
    CREATE POLICY lotes_por_org ON lotes_ganado
      USING (finca_id IN (
        SELECT id FROM fincas
        WHERE organizacion_id = NULLIF(current_setting('app.current_org', true), '')::uuid
      ));

    ALTER TABLE eventos_pastoreo ENABLE ROW LEVEL SECURITY;
    CREATE POLICY eventos_por_org ON eventos_pastoreo
      USING (potrero_id IN (
        SELECT p.id FROM potreros p JOIN fincas f ON f.id = p.finca_id
        WHERE f.organizacion_id = NULLIF(current_setting('app.current_org', true), '')::uuid
      ));

    ALTER TABLE lecturas_ndvi ENABLE ROW LEVEL SECURITY;
    CREATE POLICY ndvi_por_org ON lecturas_ndvi
      USING (potrero_id IN (
        SELECT p.id FROM potreros p JOIN fincas f ON f.id = p.finca_id
        WHERE f.organizacion_id = NULLIF(current_setting('app.current_org', true), '')::uuid
      ));

    -- ---- Seeds: especies de los Llanos/Casanare (valores de partida, a
    -- calibrar con datos reales en fase 6; temp_base ~C4 tropicales) ----
    INSERT INTO especies_pasto
      (nombre, temp_base, temp_optima_min, temp_optima_max, tasa_max_crecimiento,
       dias_descanso_ideal, curva_k, gdd_optimo_diario)
    VALUES
      ('Brachiaria decumbens',              12, 25, 35, 70, 28, 0.08, 14),
      ('Brachiaria brizantha (Marandú)',    12, 25, 35, 85, 32, 0.08, 14),
      ('Panicum maximum (Mombasa)',         13, 26, 36, 95, 30, 0.09, 15),
      ('Cynodon nlemfuensis (Estrella)',    11, 24, 34, 75, 25, 0.08, 13),
      ('Sabana nativa (Trachypogon)',       12, 24, 34, 35, 45, 0.05, 12);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS eventos_dominio, lecturas_ndvi, eventos_pastoreo,
      lotes_ganado, registros_clima, potreros, especies_pasto, fincas,
      estaciones_clima, organizaciones CASCADE;
    DROP FUNCTION IF EXISTS potreros_actualizar_area();
    """)
