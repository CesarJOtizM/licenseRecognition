import logging
from collections.abc import Iterator
from unittest.mock import create_autospec

import pytest
from conftest import TEST_JWT_SECRET
from fastapi.testclient import TestClient
from porteria_api.app import create_app
from porteria_api.config import Settings
from porteria_api.db import get_session
from sqlalchemy.orm import Session

# Nadie escucha en el puerto 1: la conexión se rechaza enseguida.
UNREACHABLE_URL = "postgresql+psycopg://porteria:porteria@127.0.0.1:1/porteria"


def test_health_responde_200_si_la_base_contesta() -> None:
    session = create_autospec(Session, instance=True)

    def override() -> Iterator[Session]:
        yield session

    app = create_app(Settings(database_url=UNREACHABLE_URL, jwt_secret=TEST_JWT_SECRET))
    app.dependency_overrides[get_session] = override
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    session.execute.assert_called_once()


def test_health_responde_503_sin_filtrar_el_error_si_no_hay_base(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(
        Settings(database_url=UNREACHABLE_URL, db_connect_timeout=1, jwt_secret=TEST_JWT_SECRET)
    )
    with TestClient(app) as client, caplog.at_level(logging.WARNING):
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}
    assert "Base de datos no disponible" in caplog.text
