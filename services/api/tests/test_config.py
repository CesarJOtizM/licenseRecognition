import pytest
from porteria_api.config import DEFAULT_DATABASE_URL, Settings
from pydantic import ValidationError


def test_sin_variables_de_entorno_usa_los_valores_por_defecto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DB_CONNECT_TIMEOUT", raising=False)

    settings = Settings()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert DEFAULT_DATABASE_URL == "postgresql+psycopg://porteria:porteria@127.0.0.1:5432/porteria"
    assert settings.db_connect_timeout == 3


def test_las_variables_de_entorno_ganan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/otra")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "7")

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://u:p@db:5432/otra"
    assert settings.db_connect_timeout == 7


def test_el_timeout_de_conexion_debe_ser_positivo() -> None:
    with pytest.raises(ValidationError):
        Settings(db_connect_timeout=0)
