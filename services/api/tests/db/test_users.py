"""Restricciones de usuarios: nombre de usuario, rol, estado y vínculo con el residente."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest
from porteria_api.models import Base, Resident, Tower, Unit, User, UserRole, UserStatus
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid_utils.compat import uuid7

pytestmark = pytest.mark.db

FAKE_HASH = "no-es-un-hash-real"

INSERT_USER = (
    "INSERT INTO users (id, username, password_hash, full_name, role, status, resident_id)"
    " VALUES (:id, :username, 'hash', 'Ana', :role, :status, :resident_id)"
)


def _add[M: Base](session: Session, row: M) -> M:
    session.add(row)
    session.flush()
    return row


@contextmanager
def _violates(constraint: str) -> Iterator[None]:
    with pytest.raises(IntegrityError) as exc_info:
        yield
    orig = exc_info.value.orig
    assert isinstance(orig, psycopg.Error)
    assert orig.diag.constraint_name == constraint


@pytest.fixture
def resident(db_session: Session) -> Resident:
    tower = _add(db_session, Tower(name="Torre 1"))
    unit = _add(db_session, Unit(tower_id=tower.id, number="101"))
    return _add(db_session, Resident(unit_id=unit.id, full_name="Ana Gómez"))


def _user(
    username: str = "ana",
    role: UserRole = UserRole.GUARD,
    resident: Resident | None = None,
) -> User:
    return User(
        username=username, password_hash=FAKE_HASH, full_name="Ana", role=role, resident=resident
    )


def _raw_user(
    session: Session,
    *,
    username: str = "ana",
    role: str = "guard",
    status: str = "active",
    resident_id: object = None,
) -> None:
    session.execute(
        text(INSERT_USER),
        {
            "id": uuid7(),
            "username": username,
            "role": role,
            "status": status,
            "resident_id": resident_id,
        },
    )


def test_un_usuario_se_guarda_con_sus_valores_por_defecto(db_session: Session) -> None:
    user = _add(db_session, _user())

    stored = db_session.execute(
        text("SELECT role, status, token_version, last_login_at FROM users WHERE id = :id"),
        {"id": user.id},
    ).one()

    assert tuple(stored) == ("guard", "active", 0, None)
    assert user.status is UserStatus.ACTIVE


@pytest.mark.parametrize("typed", ["Ana", " ANA ", "ana"])
def test_el_nombre_de_usuario_se_guarda_en_minusculas(db_session: Session, typed: str) -> None:
    user = _add(db_session, _user(username=typed))

    raw = db_session.scalar(text("SELECT username FROM users WHERE id = :id"), {"id": user.id})

    assert raw == "ana"


def test_el_nombre_de_usuario_es_unico_sin_importar_mayusculas(db_session: Session) -> None:
    _add(db_session, _user(username="ana"))

    with _violates("uq_users_username"):
        _add(db_session, _user(username="ANA"))


@pytest.mark.parametrize("username", ["Ana", "an", "-ana", "ana gómez", "ana!", ""])
def test_un_nombre_de_usuario_invalido_viola_el_check(db_session: Session, username: str) -> None:
    with _violates("ck_users_username_format"):
        _raw_user(db_session, username=username)


@pytest.mark.parametrize(
    ("constraint", "values"),
    [("ck_users_role", {"role": "device"}), ("ck_users_status", {"status": "locked"})],
)
def test_un_valor_fuera_de_la_lista_viola_el_check(
    db_session: Session, constraint: str, values: dict[str, str]
) -> None:
    with _violates(constraint):
        _raw_user(db_session, **values)


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.GUARD])
def test_solo_el_rol_residente_tiene_residente(
    db_session: Session, resident: Resident, role: UserRole
) -> None:
    with _violates("ck_users_resident_link"):
        _add(db_session, _user(role=role, resident=resident))


def test_un_usuario_residente_sin_residente_viola_el_check(db_session: Session) -> None:
    with _violates("ck_users_resident_link"):
        _add(db_session, _user(role=UserRole.RESIDENT))


def test_un_usuario_residente_apunta_a_su_residente(
    db_session: Session, resident: Resident
) -> None:
    user = _add(db_session, _user(role=UserRole.RESIDENT, resident=resident))
    db_session.expire(user)

    assert user.resident_id == resident.id
    assert user.resident is resident


def test_un_residente_tiene_a_lo_sumo_un_usuario(db_session: Session, resident: Resident) -> None:
    _add(db_session, _user(username="ana", role=UserRole.RESIDENT, resident=resident))

    with _violates("uq_users_resident_id"):
        _add(db_session, _user(username="ana2", role=UserRole.RESIDENT, resident=resident))


def test_un_usuario_con_residente_inexistente_viola_la_fk(db_session: Session) -> None:
    with _violates("fk_users_resident_id_residents"):
        _raw_user(db_session, role="resident", resident_id=uuid7())


def test_no_se_borra_un_residente_con_usuario(db_session: Session, resident: Resident) -> None:
    _add(db_session, _user(role=UserRole.RESIDENT, resident=resident))

    with _violates("fk_users_resident_id_residents"):
        db_session.execute(text("DELETE FROM residents WHERE id = :id"), {"id": resident.id})


def test_la_fk_del_residente_es_restrict_y_tiene_indice(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "SELECT c.conname, c.confdeltype, EXISTS (SELECT 1 FROM pg_index i"
            "  WHERE i.indrelid = c.conrelid AND i.indkey[0] = c.conkey[1])"
            " FROM pg_constraint c"
            " WHERE c.contype = 'f' AND c.conrelid = 'users'::regclass"
        )
    )

    assert {name: (kind, indexed) for name, kind, indexed in rows.all()} == {
        "fk_users_resident_id_residents": ("r", True),
    }
