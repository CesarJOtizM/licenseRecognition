import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from porteria_api.app import create_app
from porteria_api.config import DatabaseSettings, Settings
from porteria_api.db import create_db_engine, get_session
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

TEST_JWT_SECRET = SecretStr("secreto-de-pruebas-con-al-menos-32-caracteres")
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://porteria:porteria@127.0.0.1:5432/porteria_test"
ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"


def make_alembic_config(engine: Engine) -> Config:
    """Configuración de Alembic apuntando a la base de `engine` en vez de a Settings."""
    # configure_logger=False: el logging de alembic.ini quitaría los handlers de pytest (caplog).
    config = Config(ALEMBIC_INI, attributes={"configure_logger": False})
    url = engine.url.render_as_string(hide_password=False)
    # El .ini interpreta `%` como interpolación; hay que escaparlo.
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def _probed_engine() -> Iterator[Engine]:
    """Motor de la base de pruebas; se conecta una vez para saber si está disponible."""
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    engine = create_db_engine(DatabaseSettings(database_url=url))
    try:
        with engine.connect():
            pass
    except OperationalError:
        engine.dispose()
        message = (
            f"PostgreSQL de pruebas no disponible en {engine.url}. "
            "Levántalo con: docker compose -f infra/compose.yaml up -d --wait"
        )
        # En la CI la base es obligatoria: saltarse las pruebas ocultaría un fallo.
        if os.environ.get("API_TEST_REQUIRE_DB") == "1":
            pytest.fail(message, pytrace=False)
        pytest.skip(message)
    yield engine
    engine.dispose()


@pytest.fixture
def db_engine(request: pytest.FixtureRequest) -> Engine:
    # Sin la marca, `-m "not db"` no deselecciona la prueba y el pre-push necesitaría Docker.
    if request.node.get_closest_marker("db") is None:
        pytest.fail("Las pruebas que usan la base necesitan pytest.mark.db", pytrace=False)
    engine: Engine = request.getfixturevalue("_probed_engine")
    return engine


@pytest.fixture
def alembic_config(db_engine: Engine) -> Config:
    return make_alembic_config(db_engine)


@pytest.fixture(scope="session")
def _migrated_engine(_probed_engine: Engine) -> Engine:
    command.upgrade(make_alembic_config(_probed_engine), "head")
    return _probed_engine


@pytest.fixture
def migrated_engine(db_engine: Engine, request: pytest.FixtureRequest) -> Engine:
    """La base de pruebas con todas las migraciones aplicadas (una vez por sesión)."""
    engine: Engine = request.getfixturevalue("_migrated_engine")
    return engine


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """Sesión dentro de una transacción que se deshace al terminar la prueba."""
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        # create_savepoint: un commit() del código bajo prueba no confirma la transacción externa.
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(migrated_engine: Engine, db_session: Session) -> Iterator[TestClient]:
    """Cliente HTTP cuya sesión por petición es `db_session`."""
    url = migrated_engine.url.render_as_string(hide_password=False)
    app = create_app(Settings(database_url=url, jwt_secret=TEST_JWT_SECRET))
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
