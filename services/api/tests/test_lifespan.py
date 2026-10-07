from unittest.mock import create_autospec

import porteria_api.app as app_module
import pytest
from fastapi.testclient import TestClient
from porteria_api.app import create_app
from porteria_api.config import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session


def test_el_motor_se_crea_al_arrancar_y_se_libera_al_apagar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_autospec(Engine, instance=True)
    monkeypatch.setattr(app_module, "create_db_engine", lambda settings: engine)

    app = create_app(Settings())
    assert not hasattr(app.state, "engine")

    with TestClient(app):
        assert app.state.engine is engine
        engine.dispose.assert_not_called()

    engine.dispose.assert_called_once_with()


def test_cada_peticion_cierra_su_sesion() -> None:
    session = create_autospec(Session, instance=True)
    app = create_app(Settings())

    with TestClient(app) as client:
        app.state.sessionmaker = lambda: session
        response = client.get("/health")

    assert response.status_code == 200
    session.close.assert_called_once_with()
