"""POST y GET /users: solo administradores, sin secretos en la respuesta y con auditoría."""

import uuid

import pytest
from conftest import MakeUser, auth_headers
from fastapi.testclient import TestClient
from porteria_api.models import AuditLog, Resident, Tower, Unit, User, UserRole
from porteria_api.routes.users import http_error_for
from porteria_api.security import Passwords
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db

USER_FIELDS = {
    "id",
    "username",
    "full_name",
    "role",
    "status",
    "resident_id",
    "last_login_at",
    "created_at",
    "updated_at",
}
NEW_PASSWORD = "clave-nueva-de-bob"  # noqa: S105
FAKE_HASH = "no-es-un-hash-real"


def _count(session: Session, model: type[User] | type[AuditLog]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _free_resident(session: Session) -> Resident:
    """Un residente que todavía no tiene usuario."""
    tower = Tower(name="Torre libre")
    session.add(tower)
    session.flush()
    unit = Unit(tower_id=tower.id, number="101")
    session.add(unit)
    session.flush()
    resident = Resident(unit_id=unit.id, full_name="Residente libre")
    session.add(resident)
    session.flush()
    return resident


def _new_user(**changes: object) -> dict[str, object]:
    body: dict[str, object] = {
        "username": " Bob ",
        "password": NEW_PASSWORD,
        "full_name": " Bob Pérez ",
        "role": "guard",
    }
    body.update(changes)
    return body


@pytest.fixture
def admin_headers(make_user: MakeUser) -> dict[str, str]:
    return auth_headers(make_user(UserRole.ADMIN, username="admin"))


def test_el_admin_crea_un_guarda_y_queda_auditado(
    client: TestClient,
    make_user: MakeUser,
    db_session: Session,
    fast_passwords: Passwords,
) -> None:
    admin = make_user(UserRole.ADMIN, username="admin")

    response = client.post("/users", json=_new_user(), headers=auth_headers(admin))

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == USER_FIELDS
    assert body["username"] == "bob"
    assert body["full_name"] == "Bob Pérez"
    assert (body["role"], body["status"], body["resident_id"]) == ("guard", "active", None)
    user = db_session.get(User, uuid.UUID(body["id"]))
    assert user is not None
    assert fast_passwords.verify(NEW_PASSWORD, user.password_hash)
    log = db_session.scalars(select(AuditLog).where(AuditLog.entity_id == user.id)).one()
    assert (log.action, log.entity_type, log.actor_user_id) == ("user.created", "user", admin.id)
    assert log.before is None
    assert log.after == {
        "username": "bob",
        "full_name": "Bob Pérez",
        "role": "guard",
        "status": "active",
        "resident_id": None,
    }


def test_el_admin_crea_un_residente_ligado_a_su_residente(
    client: TestClient, admin_headers: dict[str, str], db_session: Session
) -> None:
    resident = _free_resident(db_session)

    response = client.post(
        "/users",
        json=_new_user(role="resident", resident_id=str(resident.id)),
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["resident_id"] == str(resident.id)


@pytest.mark.parametrize(("length", "expected"), [(11, 422), (12, 201), (128, 201), (129, 422)])
def test_la_contrasena_tiene_entre_12_y_128_caracteres(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
    length: int,
    expected: int,
) -> None:
    users_before = _count(db_session, User)

    response = client.post("/users", json=_new_user(password="a" * length), headers=admin_headers)

    assert response.status_code == expected, response.text
    assert _count(db_session, User) == users_before + (1 if expected == 201 else 0)


def test_un_usuario_repetido_responde_409_sin_mayusculas(
    client: TestClient, make_user: MakeUser, admin_headers: dict[str, str], db_session: Session
) -> None:
    make_user(username="bob")
    users_before, audit_before = _count(db_session, User), _count(db_session, AuditLog)

    response = client.post("/users", json=_new_user(username="BOB"), headers=admin_headers)

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists"}
    assert _count(db_session, User) == users_before
    assert _count(db_session, AuditLog) == audit_before


def test_un_residente_con_usuario_no_recibe_otro(
    client: TestClient, make_user: MakeUser, admin_headers: dict[str, str], db_session: Session
) -> None:
    taken = make_user(UserRole.RESIDENT)
    audit_before = _count(db_session, AuditLog)

    response = client.post(
        "/users",
        json=_new_user(role="resident", resident_id=str(taken.resident_id)),
        headers=admin_headers,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Resident already has a user"}
    assert _count(db_session, AuditLog) == audit_before


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"role": "resident"}, id="residente-sin-residente"),
        pytest.param({"resident_id": str(uuid.uuid4())}, id="guarda-con-residente"),
        pytest.param(
            {"role": "resident", "resident_id": str(uuid.uuid4())}, id="residente-inexistente"
        ),
        pytest.param({"role": "device"}, id="rol-desconocido"),
        pytest.param({"username": "b!"}, id="usuario-invalido"),
    ],
)
def test_datos_incoherentes_responden_422_sin_filas(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
    changes: dict[str, object],
) -> None:
    users_before, audit_before = _count(db_session, User), _count(db_session, AuditLog)

    response = client.post("/users", json=_new_user(**changes), headers=admin_headers)

    assert response.status_code == 422, response.text
    assert _count(db_session, User) == users_before
    assert _count(db_session, AuditLog) == audit_before


def test_el_listado_va_ordenado_por_usuario_y_sin_secretos(
    client: TestClient, make_user: MakeUser, admin_headers: dict[str, str]
) -> None:
    for username in ("carla", "ana", "bruno"):
        make_user(username=username)

    response = client.get("/users", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert [user["username"] for user in body] == ["admin", "ana", "bruno", "carla"]
    assert all(set(user) == USER_FIELDS for user in body)


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_sin_token_responde_401(client: TestClient, method: str) -> None:
    response = client.request(method, "/users", json=_new_user())

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("role", [UserRole.GUARD, UserRole.RESIDENT])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_guarda_y_residente_reciben_403(
    client: TestClient, make_user: MakeUser, db_session: Session, role: UserRole, method: str
) -> None:
    headers = auth_headers(make_user(role))
    users_before = _count(db_session, User)

    response = client.request(method, "/users", json=_new_user(), headers=headers)

    assert response.status_code == 403
    assert _count(db_session, User) == users_before


def test_no_se_borran_usuarios(client: TestClient, admin_headers: dict[str, str]) -> None:
    assert client.delete("/users", headers=admin_headers).status_code == 405


def test_una_restriccion_sin_traduccion_no_se_convierte_en_respuesta(
    db_session: Session,
) -> None:
    db_session.add(User(username="a", password_hash=FAKE_HASH, full_name="A", role=UserRole.GUARD))

    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()

    assert http_error_for(exc_info.value) is None
