"""Estado persistente del modelo de biomasa por potrero.

El agregado `EstimacionBiomasa` (§17.2) arrastra dos estados entre días:
la varianza del filtro de Kalman (P) y el agua en el suelo (bucket model).
Sin persistirlos, cada corrida del job diario reiniciaría la memoria del
modelo — exactamente lo que el balance hídrico debe evitar (§4.2).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-21

"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE potreros
      ADD COLUMN kalman_varianza NUMERIC,
      ADD COLUMN suelo_mm NUMERIC;
    """)


def downgrade() -> None:
    op.execute("""
    ALTER TABLE potreros
      DROP COLUMN IF EXISTS kalman_varianza,
      DROP COLUMN IF EXISTS suelo_mm;
    """)
