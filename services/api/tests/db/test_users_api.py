"""/users: solo administradores, sin secretos en la respuesta y con auditoría."""

import uuid

import pytest
from conftest import TEST_PASSWORD, MakeUser, auth_headers
from fastapi.testclient import TestClient
from porteria_api.models import AuditLog, Resident, Tower, Unit, User, UserRole, UserStatus
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


def test_no_se_borran_usuarios(
    client: TestClient, make_user: MakeUser, admin_headers: dict[str, str]
) -> None:
    target = make_user()

    assert client.delete("/users", headers=admin_headers).status_code == 405
    assert client.delete(f"/users/{target.id}", headers=admin_headers).status_code == 405


def test_una_restriccion_sin_traduccion_no_se_convierte_en_respuesta(
    db_session: Session,
) -> None:
    db_session.add(User(username="a", password_hash=FAKE_HASH, full_name="A", role=UserRole.GUARD))

    with pytest.raises(IntegrityError) as exc_info:
        db_session.flush()

    assert http_error_for(exc_info.value) is None


def _logs(session: Session, user: User) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.entity_id == user.id)))


def test_deshabilitar_corta_el_acceso_y_reactivar_no_revive_el_token(
    client: TestClient, make_user: MakeUser, admin_headers: dict[str, str]
) -> None:
    guard = make_user()
    old_token = auth_headers(guard)

    response = client.patch(
        f"/users/{guard.id}", json={"status": "disabled"}, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    assert set(response.json()) == USER_FIELDS
    assert response.json()["status"] == "disabled"
    assert client.get("/auth/me", headers=old_token).status_code == 401
    client.patch(f"/users/{guard.id}", json={"status": "active"}, headers=admin_headers)
    assert client.get("/auth/me", headers=old_token).status_code == 401
    assert client.get("/auth/me", headers=auth_headers(guard)).status_code == 200


def test_cambiar_el_rol_deja_una_fila_con_antes_y_despues(
    client: TestClient, make_user: MakeUser, db_session: Session
) -> None:
    admin = make_user(UserRole.ADMIN, username="admin")
    guard = make_user(username="bob")

    response = client.patch(
        f"/users/{guard.id}", json={"role": "admin"}, headers=auth_headers(admin)
    )

    assert response.status_code == 200, response.text
    [log] = _logs(db_session, guard)
    assert (log.action, log.actor_user_id) == ("user.updated", admin.id)
    assert (log.before or {}).get("role") == "guard"
    assert log.after == {**(log.before or {}), "role": "admin"}


def test_guarda_a_residente_y_de_vuelta_con_null_explicito(
    client: TestClient, make_user: MakeUser, admin_headers: dict[str, str], db_session: Session
) -> None:
    guard, resident = make_user(), _free_resident(db_session)
    to_resident = {"role": "resident", "resident_id": str(resident.id)}

    first = client.patch(f"/users/{guard.id}", json=to_resident, headers=admin_headers)
    back = client.patch(
        f"/users/{guard.id}", json={"role": "guard", "resident_id": None}, headers=admin_headers
    )

    assert first.json()["resident_id"] == str(resident.id), first.text
    assert (back.json()["role"], back.json()["resident_id"]) == ("guard", None), back.text


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        pytest.param({"role": "resident"}, 422, id="residente-sin-residente"),
        pytest.param(
            {"role": "resident", "resident_id": str(uuid.uuid4())}, 422, id="residente-inexistente"
        ),
        pytest.param({"role": "resident", "resident_id": "taken"}, 409, id="residente-ocupado"),
        pytest.param({"full_name": None}, 422, id="nombre-null"),
        pytest.param({"status": "borrado"}, 422, id="estado-desconocido"),
    ],
)
def test_un_patch_rechazado_no_cambia_nada_ni_audita(
    client: TestClient,
    make_user: MakeUser,
    admin_headers: dict[str, str],
    db_session: Session,
    changes: dict[str, object],
    expected: int,
) -> None:
    guard = make_user()
    if changes.get("resident_id") == "taken":
        changes["resident_id"] = str(make_user(UserRole.RESIDENT).resident_id)
    full_name, audit_before = guard.full_name, _count(db_session, AuditLog)

    response = client.patch(f"/users/{guard.id}", json=changes, headers=admin_headers)

    assert response.status_code == expected, response.text
    db_session.refresh(guard)
    assert (guard.role, guard.resident_id, guard.full_name) == (UserRole.GUARD, None, full_name)
    assert _count(db_session, AuditLog) == audit_before


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [("PATCH", "", {"full_name": "Nadie"}), ("POST", "/password", {"new_password": NEW_PASSWORD})],
)
def test_un_usuario_inexistente_responde_404(
    client: TestClient, admin_headers: dict[str, str], method: str, suffix: str, body: object
) -> None:
    response = client.request(
        method, f"/users/{uuid.uuid4()}{suffix}", json=body, headers=admin_headers
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


@pytest.mark.parametrize("changes", [{"status": "disabled"}, {"role": "guard"}])
def test_el_admin_no_se_deshabilita_ni_se_quita_el_rol(
    client: TestClient, make_user: MakeUser, db_session: Session, changes: dict[str, str]
) -> None:
    admin = make_user(UserRole.ADMIN, username="admin")

    response = client.patch(f"/users/{admin.id}", json=changes, headers=auth_headers(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "You cannot disable or demote your own account"}
    db_session.refresh(admin)
    assert (admin.role, admin.status) == (UserRole.ADMIN, UserStatus.ACTIVE)
    assert _logs(db_session, admin) == []


def test_el_admin_si_cambia_su_propio_nombre(
    client: TestClient, make_user: MakeUser, db_session: Session
) -> None:
    admin = make_user(UserRole.ADMIN, username="admin")

    response = client.patch(
        f"/users/{admin.id}",
        json={"full_name": "Ana Admin", "role": "admin", "status": "active"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200, response.text
    [log] = _logs(db_session, admin)
    assert log.after == {**(log.before or {}), "full_name": "Ana Admin"}


@pytest.mark.parametrize("changes", [{}, {"full_name": "Bob", "role": "guard", "status": "active"}])
def test_un_patch_sin_cambios_no_audita(
    client: TestClient,
    make_user: MakeUser,
    admin_headers: dict[str, str],
    db_session: Session,
    changes: dict[str, str],
) -> None:
    guard = make_user()
    guard.full_name = "Bob"
    db_session.flush()

    response = client.patch(f"/users/{guard.id}", json=changes, headers=admin_headers)

    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Bob"
    assert _logs(db_session, guard) == []


def test_cambiar_la_contrasena_invalida_tokens_y_audita_sin_secretos(
    client: TestClient, make_user: MakeUser, db_session: Session
) -> None:
    admin = make_user(UserRole.ADMIN, username="admin")
    guard = make_user(username="bob")
    old_token = auth_headers(guard)

    response = client.post(
        f"/users/{guard.id}/password",
        json={"new_password": NEW_PASSWORD},
        headers=auth_headers(admin),
    )

    assert response.status_code == 204, response.text
    assert response.content == b""
    db_session.refresh(guard)
    assert guard.token_version == 1
    assert client.get("/auth/me", headers=old_token).status_code == 401
    old_login = client.post("/auth/login", data={"username": "bob", "password": TEST_PASSWORD})
    assert old_login.status_code == 401
    new_login = client.post("/auth/login", data={"username": "bob", "password": NEW_PASSWORD})
    assert new_login.status_code == 200
    [log] = _logs(db_session, guard)
    assert (log.action, log.actor_user_id) == ("user.password_reset", admin.id)
    assert (log.before, log.after) == (None, None)


def test_una_contrasena_corta_no_cambia_nada(
    client: TestClient, make_user: MakeUser, admin_headers: dict[str, str], db_session: Session
) -> None:
    guard = make_user()

    response = client.post(
        f"/users/{guard.id}/password", json={"new_password": "corta"}, headers=admin_headers
    )

    assert response.status_code == 422
    db_session.refresh(guard)
    assert guard.token_version == 0
    assert _logs(db_session, guard) == []
