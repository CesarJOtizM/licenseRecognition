"""El usuario actual se recarga de la base en cada petición: el token solo dice quién es."""

from datetime import UTC, datetime, timedelta

import pytest
from conftest import MakeUser, auth_headers
from fastapi import APIRouter
from fastapi.testclient import TestClient
from porteria_api.auth import CurrentUser
from porteria_api.models import ResidentStatus, User, UserRole, UserStatus
from sqlalchemy.orm import Session
from uuid_utils.compat import uuid7

pytestmark = pytest.mark.db

router = APIRouter()


@router.get("/prueba/yo")
def yo(user: CurrentUser) -> dict[str, str]:
    return {"username": user.username}


@pytest.fixture
def api(client: TestClient) -> TestClient:
    client.app.include_router(router)  # type: ignore[attr-defined]
    return client


def _assert_401(api: TestClient, headers: dict[str, str]) -> None:
    response = api.get("/prueba/yo", headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.GUARD, UserRole.RESIDENT])
def test_un_token_vigente_devuelve_al_usuario(
    api: TestClient, make_user: MakeUser, role: UserRole
) -> None:
    user = make_user(role, username=f"ana-{role.value}")

    response = api.get("/prueba/yo", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {"username": f"ana-{role.value}"}


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="sin-token"),
        pytest.param({"Authorization": "Bearer basura"}, id="malformado"),
    ],
)
def test_sin_token_valido_responde_401(api: TestClient, headers: dict[str, str]) -> None:
    _assert_401(api, headers)


def test_un_token_vencido_responde_401(api: TestClient, make_user: MakeUser) -> None:
    user = make_user()

    _assert_401(api, auth_headers(user, now=datetime.now(UTC) - timedelta(hours=1)))


def test_un_usuario_inexistente_responde_401(api: TestClient) -> None:
    _assert_401(api, auth_headers(User(id=uuid7(), token_version=0)))


def test_un_token_de_version_anterior_responde_401(
    api: TestClient, make_user: MakeUser, db_session: Session
) -> None:
    user = make_user()
    old_headers = auth_headers(user)
    user.token_version += 1
    db_session.flush()

    _assert_401(api, old_headers)
    assert api.get("/prueba/yo", headers=auth_headers(user)).status_code == 200


def test_un_usuario_deshabilitado_responde_401(
    api: TestClient, make_user: MakeUser, db_session: Session
) -> None:
    user = make_user()
    headers = auth_headers(user)
    user.status = UserStatus.DISABLED
    db_session.flush()

    _assert_401(api, headers)


def test_un_residente_inactivo_responde_401_aunque_el_token_sea_vigente(
    api: TestClient, make_user: MakeUser, db_session: Session
) -> None:
    user = make_user(UserRole.RESIDENT)
    headers = auth_headers(user)
    assert api.get("/prueba/yo", headers=headers).status_code == 200
    assert user.resident is not None
    user.resident.status = ResidentStatus.INACTIVE
    db_session.flush()

    _assert_401(api, headers)
