"""Pruebas de las migraciones. No usan `db_session`: el DDL esperaría a sus bloqueos."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from porteria_api.models import Base
from sqlalchemy import Column, Engine, Integer, MetaData, Table

pytestmark = pytest.mark.db


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def test_stairway_cada_revision_sube_baja_y_vuelve_a_subir(
    alembic_config: Config, db_engine: Engine
) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    revisions = list(reversed(list(script.walk_revisions())))
    assert revisions, "no hay revisiones"

    command.downgrade(alembic_config, "base")
    assert _current_revision(db_engine) is None

    for revision in revisions:
        command.upgrade(alembic_config, revision.revision)
        command.downgrade(alembic_config, "-1")
        command.upgrade(alembic_config, revision.revision)

    # Las demás pruebas cuentan con la base en head.
    assert _current_revision(db_engine) == script.get_current_head()


def test_sin_url_en_el_ini_usa_database_url_de_settings(
    alembic_config: Config, db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", db_engine.url.render_as_string(hide_password=False))
    config = Config(alembic_config.config_file_name, attributes={"configure_logger": False})

    command.downgrade(config, "base")
    assert _current_revision(db_engine) is None
    command.upgrade(config, "head")
    assert _current_revision(db_engine) == ScriptDirectory.from_config(config).get_current_head()


def _drift(engine: Engine, metadata: MetaData) -> list[object]:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return list(compare_metadata(context, metadata))


def test_los_modelos_coinciden_con_las_migraciones(
    alembic_config: Config, db_engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")

    assert _drift(db_engine, Base.metadata) == []


def test_el_drift_detecta_una_tabla_sin_migracion(
    alembic_config: Config, db_engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")
    # Copia de los modelos más una tabla nueva: la única diferencia debe ser esa tabla.
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for table in Base.metadata.sorted_tables:
        table.to_metadata(metadata)
    Table("sin_migracion", metadata, Column("id", Integer, primary_key=True))

    (diff,) = _drift(db_engine, metadata)

    assert isinstance(diff, tuple)
    assert diff[0] == "add_table"
    assert diff[1].name == "sin_migracion"
