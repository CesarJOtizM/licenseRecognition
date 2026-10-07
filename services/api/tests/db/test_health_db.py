import pytest
from fastapi.testclient import TestClient
from porteria_api.app import create_app
from porteria_api.config import Settings
from sqlalchemy import Engine

pytestmark = pytest.mark.db


def test_health_con_postgres_real_responde_ok(db_engine: Engine) -> None:
    url = db_engine.url.render_as_string(hide_password=False)
    app = create_app(Settings(database_url=url))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
