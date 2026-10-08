"""Entorno de Alembic: a qué base conectarse y contra qué modelos comparar."""

from logging.config import fileConfig

from alembic import context
from porteria_api.config import DatabaseSettings
from porteria_api.models import Base
from sqlalchemy import create_engine, pool

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
settings = DatabaseSettings()


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: escribe el SQL sin conectarse a la base."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Sin connect_timeout, en Windows una base caída deja el comando esperando indefinidamente.
    engine = create_engine(
        _database_url(),
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": settings.db_connect_timeout},
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
