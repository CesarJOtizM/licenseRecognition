"""migrations/env.py sin base de datos: URL desde Settings y modo offline (solo genera SQL)."""

import io
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import OperationalError

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"


def test_con_la_base_caida_falla_en_vez_de_quedarse_esperando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://porteria:porteria@127.0.0.1:1/x")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "1")
    config = Config(ALEMBIC_INI, attributes={"configure_logger": False})

    with pytest.raises(OperationalError):
        command.upgrade(config, "head")


def test_modo_offline_genera_el_sql_de_las_revisiones(monkeypatch: pytest.MonkeyPatch) -> None:
    # Alembic no usa el secreto de los tokens: la CI corre migraciones sin JWT_SECRET.
    monkeypatch.delenv("JWT_SECRET", raising=False)
    output = io.StringIO()
    config = Config(ALEMBIC_INI, output_buffer=output, attributes={"configure_logger": False})

    command.upgrade(config, "head", sql=True)

    assert "INSERT INTO alembic_version (version_num) VALUES ('0001')" in output.getvalue()
