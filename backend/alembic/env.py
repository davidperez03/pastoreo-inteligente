import os

from sqlalchemy import create_engine

from alembic import context

config = context.config


def _url() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql://srp:srp@localhost:5432/srp")
    # alembic usa driver sync (psycopg); normalizamos el esquema del DSN.
    # Algunos proveedores (Supabase, Heroku) entregan "postgres://" en vez
    # de "postgresql://" — ambos son válidos para libpq pero SQLAlchemy solo
    # reconoce el segundo como prefijo a sustituir.
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
