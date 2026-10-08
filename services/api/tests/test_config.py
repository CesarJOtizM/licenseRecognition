import pytest
from conftest import TEST_JWT_SECRET
from porteria_api.config import DEFAULT_DATABASE_URL, DatabaseSettings, Settings
from pydantic import SecretStr, ValidationError

ENV_VARS = ("DATABASE_URL", "DB_CONNECT_TIMEOUT", "JWT_ALGORITHM", "ACCESS_TOKEN_MINUTES")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JWT_SECRET", TEST_JWT_SECRET.get_secret_value())


def test_sin_variables_de_entorno_usa_los_valores_por_defecto() -> None:
    settings = Settings()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert DEFAULT_DATABASE_URL == "postgresql+psycopg://porteria:porteria@127.0.0.1:5432/porteria"
    assert settings.db_connect_timeout == 3
    assert settings.jwt_secret == TEST_JWT_SECRET
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_minutes == 30


def test_las_variables_de_entorno_ganan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/otra")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "7")
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "5")

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://u:p@db:5432/otra"
    assert settings.db_connect_timeout == 7
    assert settings.access_token_minutes == 5


def test_el_timeout_de_conexion_debe_ser_positivo() -> None:
    with pytest.raises(ValidationError):
        Settings(db_connect_timeout=0)


def test_sin_jwt_secret_la_api_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET")

    with pytest.raises(ValidationError) as excinfo:
        Settings()

    assert [error["loc"] for error in excinfo.value.errors()] == [("jwt_secret",)]


def test_el_secreto_necesita_al_menos_32_caracteres() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Settings(jwt_secret=SecretStr("x" * 31))

    assert [error["loc"] for error in excinfo.value.errors()] == [("jwt_secret",)]
    assert Settings(jwt_secret=SecretStr("x" * 32)).jwt_secret.get_secret_value() == "x" * 32


def test_el_secreto_no_aparece_al_imprimir_la_configuracion() -> None:
    settings = Settings()

    secret = TEST_JWT_SECRET.get_secret_value()
    assert secret not in repr(settings)
    assert secret not in str(settings)
    assert secret not in settings.model_dump_json()


@pytest.mark.parametrize("minutes", [0, 1441])
def test_la_duracion_del_token_tiene_limites(minutes: int) -> None:
    with pytest.raises(ValidationError):
        Settings(access_token_minutes=minutes)


@pytest.mark.parametrize("algorithm", ["none", "RS256", "HS512"])
def test_solo_se_acepta_hs256(monkeypatch: pytest.MonkeyPatch, algorithm: str) -> None:
    monkeypatch.setenv("JWT_ALGORITHM", algorithm)

    with pytest.raises(ValidationError):
        Settings()


def test_la_configuracion_de_base_de_datos_no_pide_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JWT_SECRET")

    settings = DatabaseSettings()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert not hasattr(settings, "jwt_secret")
