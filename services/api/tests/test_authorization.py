"""401 frente a 403 y la regla de quién puede entrar, sin base de datos."""

from collections.abc import Iterator

import pytest
from conftest import TEST_JWT_SECRET
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from porteria_api.app import create_app
from porteria_api.auth import AdminUser, get_current_user, is_login_allowed, require_roles
from porteria_api.config import Settings
from porteria_api.models import Resident, ResidentStatus, User, UserRole, UserStatus
from porteria_api.security import Passwords

router = APIRouter()


@router.get("/solo-admin")
def solo_admin(user: AdminUser) -> dict[str, str]:
    return {"role": user.role}


@router.get("/porteria", dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.GUARD))])
def porteria() -> dict[str, bool]:
    return {"ok": True}


def _user(role: UserRole, *, status: UserStatus = UserStatus.ACTIVE) -> User:
    return User(username=f"{role.value}1", full_name="Prueba", role=role, status=status)


@pytest.fixture
def app_client(fast_passwords: Passwords) -> Iterator[TestClient]:
    app = create_app(Settings(jwt_secret=TEST_JWT_SECRET), passwords=fast_passwords)
    app.include_router(router)
    with TestClient(app) as client:
        yield client


def _login_as(client: TestClient, user: User) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: user  # type: ignore[attr-defined]


def test_create_app_guarda_settings_y_passwords(fast_passwords: Passwords) -> None:
    settings = Settings(jwt_secret=TEST_JWT_SECRET)

    app = create_app(settings, passwords=fast_passwords)

    assert app.state.settings is settings
    assert app.state.passwords is fast_passwords


def test_sin_passwords_create_app_usa_argon2_por_defecto() -> None:
    app = create_app(Settings(jwt_secret=TEST_JWT_SECRET))

    assert isinstance(app.state.passwords, Passwords)
    assert "m=65536,t=3,p=4" in app.state.passwords.hash("contrasena-real")


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="sin-token"),
        pytest.param({"Authorization": "Bearer no.es.un-jwt"}, id="token-malformado"),
        pytest.param({"Authorization": "Basic YWRtaW46eA=="}, id="otro-esquema"),
    ],
)
def test_sin_token_valido_responde_401_con_www_authenticate(
    app_client: TestClient, headers: dict[str, str]
) -> None:
    response = app_client.get("/solo-admin", headers=headers)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("role", [UserRole.GUARD, UserRole.RESIDENT])
def test_un_rol_no_permitido_responde_403(app_client: TestClient, role: UserRole) -> None:
    _login_as(app_client, _user(role))

    response = app_client.get("/solo-admin")

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_el_rol_permitido_pasa(app_client: TestClient) -> None:
    _login_as(app_client, _user(UserRole.ADMIN))

    response = app_client.get("/solo-admin")

    assert response.status_code == 200
    assert response.json() == {"role": "admin"}


@pytest.mark.parametrize(
    ("role", "expected"),
    [(UserRole.ADMIN, 200), (UserRole.GUARD, 200), (UserRole.RESIDENT, 403)],
)
def test_require_roles_acepta_varios_roles(
    app_client: TestClient, role: UserRole, expected: int
) -> None:
    _login_as(app_client, _user(role))

    assert app_client.get("/porteria").status_code == expected


@pytest.mark.parametrize(
    ("user", "allowed"),
    [
        pytest.param(_user(UserRole.GUARD), True, id="guarda-activo"),
        pytest.param(_user(UserRole.ADMIN, status=UserStatus.DISABLED), False, id="deshabilitado"),
    ],
)
def test_is_login_allowed_segun_el_estado(user: User, allowed: bool) -> None:
    assert is_login_allowed(user) is allowed


@pytest.mark.parametrize(
    ("resident_status", "allowed"),
    [(ResidentStatus.ACTIVE, True), (ResidentStatus.INACTIVE, False)],
)
def test_is_login_allowed_segun_el_residente(
    resident_status: ResidentStatus, allowed: bool
) -> None:
    user = _user(UserRole.RESIDENT)
    user.resident = Resident(full_name="Ana", status=resident_status)

    assert is_login_allowed(user) is allowed
