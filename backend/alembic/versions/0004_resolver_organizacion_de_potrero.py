"""Función de resolución de organización por potrero (bootstrapping de RLS).

Los handlers de eventos de dominio que corren en el proceso de la API (no en
el worker) reaccionan a eventos que solo traen `potrero_id`; necesitan saber
la organización dueña ANTES de poder fijar `app.current_org` para el resto de
la operación — un problema de huevo y gallina que una consulta normal contra
tablas con RLS no puede resolver (sin `app.current_org` fijado, `potreros` y
`fincas` devuelven cero filas para cualquier valor).

La solución estándar en Postgres es una función SECURITY DEFINER, acotada a
esta única consulta de solo lectura (nunca expone más que el UUID de
organización de un potrero dado) — no un bypass general de RLS para el rol.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-21

"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION organizacion_de_potrero(p_potrero_id UUID)
    RETURNS UUID
    LANGUAGE sql
    SECURITY DEFINER
    SET search_path = public
    STABLE
    AS $$
      SELECT f.organizacion_id
      FROM potreros p
      JOIN fincas f ON f.id = p.finca_id
      WHERE p.id = p_potrero_id;
    $$;

    -- No es PUBLIC: solo el rol de aplicación puede invocarla. El GRANT es
    -- condicional porque "srp_app" existe en Supabase (creado por
    -- scripts/crear_rol_app.py) pero no en el Postgres local del
    -- docker-compose, donde el rol de desarrollo ("srp") ya es owner/
    -- superuser y no lo necesita — sin este condicional, la migración
    -- fallaría en local con "role srp_app does not exist".
    REVOKE ALL ON FUNCTION organizacion_de_potrero(UUID) FROM PUBLIC;
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'srp_app') THEN
        GRANT EXECUTE ON FUNCTION organizacion_de_potrero(UUID) TO srp_app;
      END IF;
    END
    $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS organizacion_de_potrero(UUID);")
