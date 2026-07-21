"""Tabla usuarios: puente entre identidad de Supabase Auth y organizacion (§10).

`id` es por convención el mismo UUID que `auth.users.id` en Supabase — sin FK
dura a `auth.users` para que la migración siga aplicando tal cual sobre un
Postgres local sin ese esquema (docker-compose de desarrollo).

Deliberadamente SIN RLS: la única consulta que hace la app sobre esta tabla
es "dame la fila de ESTE id", con el id ya verificado por la firma del JWT de
Supabase — no hay forma de que un caller vea la fila de otro usuario, así que
una política de RLS aquí no añade aislamiento real, solo complejidad (y
crearía el problema de huevo-y-gallina de no poder resolver la organización
antes de conocerla).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-21

"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE usuarios (
      id UUID PRIMARY KEY,  -- = auth.users.id en Supabase (convención, sin FK cross-schema)
      organizacion_id UUID NOT NULL REFERENCES organizaciones(id),
      rol TEXT NOT NULL DEFAULT 'operador' CHECK (rol IN ('admin', 'operador')),
      email TEXT,  -- copia de conveniencia para administración; no es la fuente de verdad
      creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE INDEX usuarios_organizacion_idx ON usuarios (organizacion_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS usuarios;")
