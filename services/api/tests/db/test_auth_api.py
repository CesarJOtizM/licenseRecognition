"""POST /auth/login y GET /auth/me: el mismo 401 para cualquier fallo y nada secreto en /me."""

import logging

import pytest
from conftest import TEST_PASSWORD, TEST_TOKEN_MINUTES, MakeUser, auth_headers
from fastapi.testclient import TestClient
from porteria_api.models import AuditLog, ResidentStatus, User, UserRole, UserStatus
from porteria_api.security import Passwords
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db

LOGIN_ERROR = {"detail": "Incorrect username or password"}
ME_FIELDS = {"id", "username", "role", "resident_id", "unit_id"}
WRONG_PASSWORD = "otra-contrasena-larga"  # noqa: S105


def _post_login(api: TestClient, username: str, password: str = TEST_PASSWORD) -> dict[str, object]:
    response = api.post("/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def _bearer(body: dict[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {body['access_token']}"}


def _audit_rows(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(AuditLog)) or 0


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.GUARD, UserRole.RESIDENT])
def test_login_correcto_entrega_un_token_que_sirve_en_me(
    client: TestClient, make_user: MakeUser, db_session: Session, role: UserRole
) -> None:
    user = make_user(role, username=f"ana-{role.value}")
    audit_before = _audit_rows(db_session)

    body = _post_login(client, f"ana-{role.value}")

    assert body["token_type"] == "bearer"  # noqa: S105
    assert body["expires_in"] == TEST_TOKEN_MINUTES * 60
    me = client.get("/auth/me", headers=_bearer(body))
    assert me.status_code == 200
    assert me.json()["username"] == f"ana-{role.value}"
    db_session.refresh(user)
    assert user.last_login_at is not None
    assert _audit_rows(db_session) == audit_before


def test_el_usuario_no_distingue_mayusculas(client: TestClient, make_user: MakeUser) -> None:
    make_user(username="ana")

    body = _post_login(client, " ANA ")

    assert client.get("/auth/me", headers=_bearer(body)).json()["username"] == "ana"


@pytest.mark.parametrize(
    ("role", "username", "password", "status", "resident_status"),
    [
        pytest.param(
            UserRole.GUARD, "ana", WRONG_PASSWORD, UserStatus.ACTIVE, None, id="clave-incorrecta"
        ),
        pytest.param(
            UserRole.GUARD, "nadie", TEST_PASSWORD, UserStatus.ACTIVE, None, id="inexistente"
        ),
        pytest.param(
            UserRole.GUARD, "ana", TEST_PASSWORD, UserStatus.DISABLED, None, id="deshabilitado"
        ),
        pytest.param(
            UserRole.RESIDENT,
            "ana",
            TEST_PASSWORD,
            UserStatus.ACTIVE,
            ResidentStatus.INACTIVE,
            id="residente-inactivo",
        ),
    ],
)
def test_cualquier_fallo_de_login_responde_el_mismo_401(
    client: TestClient,
    make_user: MakeUser,
    db_session: Session,
    role: UserRole,
    username: str,
    password: str,
    status: UserStatus,
    resident_status: ResidentStatus | None,
) -> None:
    user = make_user(role, username="ana", status=status)
    if resident_status is not None:
        assert user.resident is not None
        user.resident.status = resident_status
        db_session.flush()
    audit_before = _audit_rows(db_session)

    response = client.post("/auth/login", data={"username": username, "password": password})

    assert response.status_code == 401
    assert response.json() == LOGIN_ERROR
    assert response.headers["WWW-Authenticate"] == "Bearer"
    db_session.refresh(user)
    assert user.last_login_at is None
    assert _audit_rows(db_session) == audit_before


def test_un_usuario_inexistente_gasta_un_hash_de_relleno(
    client: TestClient, fast_passwords: Passwords, monkeypatch: pytest.MonkeyPatch
) -> None:
    checked: list[str] = []
    monkeypatch.setattr(fast_passwords, "verify_dummy", checked.append)

    client.post("/auth/login", data={"username": "nadie", "password": WRONG_PASSWORD})

    assert checked == [WRONG_PASSWORD]


def test_el_log_tiene_el_usuario_pero_no_la_contrasena(
    client: TestClient, make_user: MakeUser, caplog: pytest.LogCaptureFixture
) -> None:
    make_user(username="ana")
    caplog.set_level(logging.INFO, logger="porteria_api")

    client.post("/auth/login", data={"username": "ana", "password": WRONG_PASSWORD})
    _post_login(client, "ana")

    messages = [record.getMessage() for record in caplog.records]
    assert len(messages) == 2
    assert all("ana" in message for message in messages)
    assert not any(WRONG_PASSWORD in m or TEST_PASSWORD in m for m in messages)


def test_me_de_un_residente_trae_su_residente_y_su_unidad(
    client: TestClient, make_user: MakeUser
) -> None:
    user = make_user(UserRole.RESIDENT, username="ana")
    assert user.resident is not None

    response = client.get("/auth/me", headers=auth_headers(user))

    assert response.json() == {
        "id": str(user.id),
        "username": "ana",
        "role": "resident",
        "resident_id": str(user.resident.id),
        "unit_id": str(user.resident.unit_id),
    }


def test_me_de_un_guarda_no_expone_hash_ni_version(client: TestClient, make_user: MakeUser) -> None:
    user = make_user(UserRole.GUARD)

    body = client.get("/auth/me", headers=auth_headers(user)).json()

    assert set(body) == ME_FIELDS
    assert body["role"] == "guard"
    assert body["resident_id"] is None
    assert body["unit_id"] is None


def test_me_rechaza_un_token_de_version_anterior(
    client: TestClient, make_user: MakeUser, db_session: Session
) -> None:
    user: User = make_user()
    body = _post_login(client, user.username)
    user.token_version += 1
    db_session.flush()

    response = client.get("/auth/me", headers=_bearer(body))

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert client.get("/auth/me").status_code == 401
