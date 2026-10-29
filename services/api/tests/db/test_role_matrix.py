"""Quién puede llamar a qué: /users* solo admin, /auth/me cualquier rol, sin token 401."""

import pytest
from conftest import MakeUser, auth_headers
from fastapi.testclient import TestClient
from porteria_api.models import UserRole
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db

NEW_PASSWORD = "otra-clave-bien-larga"  # noqa: S105
# (método, ruta, cuerpo, respuesta del admin); `{id}` es un guarda que ya existe.
ENDPOINTS = [
    ("GET", "/users", None, 200),
    (
        "POST",
        "/users",
        {"username": "nuevo", "password": NEW_PASSWORD, "full_name": "N", "role": "guard"},
        201,
    ),
    ("PATCH", "/users/{id}", {"full_name": "Otro nombre"}, 200),
    ("POST", "/users/{id}/password", {"new_password": NEW_PASSWORD}, 204),
    ("GET", "/auth/me", None, 200),
]


@pytest.mark.parametrize(("method", "path", "body", "admin_status"), ENDPOINTS)
@pytest.mark.parametrize("role", [None, UserRole.ADMIN, UserRole.GUARD, UserRole.RESIDENT])
def test_matriz_de_roles(
    client: TestClient,
    make_user: MakeUser,
    role: UserRole | None,
    method: str,
    path: str,
    body: dict[str, str] | None,
    admin_status: int,
) -> None:
    target = make_user(username="objetivo")
    headers = auth_headers(make_user(role)) if role is not None else {}

    response = client.request(method, path.format(id=target.id), json=body, headers=headers)

    if role is None:
        expected = 401
    elif role is UserRole.ADMIN:
        expected = admin_status
    else:
        expected = 200 if path == "/auth/me" else 403
    assert response.status_code == expected, response.text


def test_manda_el_rol_actual_y_no_el_del_token(
    client: TestClient, make_user: MakeUser, db_session: Session
) -> None:
    admin = make_user(UserRole.ADMIN)
    headers = auth_headers(admin)
    admin.role = UserRole.GUARD
    db_session.flush()

    assert client.get("/users", headers=headers).status_code == 403
