import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from porteria_api.config import Settings
from porteria_api.db import create_db_engine
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

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
    engine = create_db_engine(Settings(database_url=url))
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
