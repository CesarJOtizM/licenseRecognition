"""Fotos de auditoría: solo campos permitidos y valores que caben en JSON."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from porteria_api.audit import USER_AUDIT_FIELDS, snapshot
from porteria_api.models import User, UserRole, UserStatus
from uuid_utils.compat import uuid7

FAKE_HASH = "no-es-un-hash-real"


def _user(**values: object) -> User:
    return User(
        username="Ana",
        password_hash=FAKE_HASH,
        full_name="Ana Gómez",
        role=UserRole.GUARD,
        status=UserStatus.ACTIVE,
        **values,
    )


def test_la_foto_de_un_usuario_tiene_solo_los_campos_permitidos() -> None:
    assert snapshot(_user(), USER_AUDIT_FIELDS) == {
        "username": "ana",
        "full_name": "Ana Gómez",
        "role": "guard",
        "status": "active",
        "resident_id": None,
    }


def test_la_foto_convierte_uuid_fechas_y_enteros() -> None:
    resident_id = uuid7()
    login = datetime(2026, 10, 28, 15, 30, tzinfo=UTC)
    user = _user(resident_id=resident_id, last_login_at=login, token_version=3)

    assert snapshot(user, ("resident_id", "last_login_at", "token_version")) == {
        "resident_id": str(resident_id),
        "last_login_at": "2026-10-28T15:30:00+00:00",
        "token_version": 3,
    }


@pytest.mark.parametrize("secret", ["password", "password_hash"])
def test_la_foto_nunca_incluye_secretos(secret: str) -> None:
    with pytest.raises(ValueError, match=secret):
        snapshot(_user(), ("username", secret))


def test_la_foto_rechaza_valores_que_no_sabe_guardar() -> None:
    with pytest.raises(TypeError, match="ratio"):
        snapshot(SimpleNamespace(ratio=0.5), ("ratio",))
