"""USR-08: `create-admin` crea un admin activo auditado con actor NULL, o no cambia nada."""

import pytest
from conftest import MakeUser
from porteria_api.cli import EXIT_REJECTED, create_admin, main
from porteria_api.models import AuditLog, User, UserRole, UserStatus
from porteria_api.security import Passwords
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db

PASSWORD = "contrasena-del-admin"  # noqa: S105


def _count(session: Session, model: type[User] | type[AuditLog]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_crea_un_admin_activo_con_argon2_y_auditoria_sin_actor(
    db_session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["create-admin", "--username", " Root ", "--full-name", "Administradora"],
        read_password=lambda _prompt: PASSWORD,
        session=db_session,
    )

    assert code == 0
    user = db_session.scalars(select(User).where(User.username == "root")).one()
    assert (user.role, user.status, user.full_name) == (
        UserRole.ADMIN,
        UserStatus.ACTIVE,
        "Administradora",
    )
    # Passwords() por defecto: los parámetros de producción, no los baratos de las pruebas.
    assert user.password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert Passwords().verify(PASSWORD, user.password_hash)
    log = db_session.scalars(select(AuditLog).where(AuditLog.entity_id == user.id)).one()
    assert (log.action, log.actor_user_id, log.entity_type, log.before) == (
        "user.created",
        None,
        "user",
        None,
    )
    assert log.after == {
        "username": "root",
        "full_name": "Administradora",
        "role": "admin",
        "status": "active",
        "resident_id": None,
    }
    out, err = capsys.readouterr()
    assert "root" in out
    assert PASSWORD not in out + err


def test_username_existente_sale_con_error_y_sin_filas_nuevas(
    db_session: Session,
    make_user: MakeUser,
    fast_passwords: Passwords,
    capsys: pytest.CaptureFixture[str],
) -> None:
    existing = make_user(UserRole.GUARD, username="root")
    users, logs = _count(db_session, User), _count(db_session, AuditLog)

    code = main(
        ["create-admin", "--username", "ROOT"],
        read_password=lambda _prompt: PASSWORD,
        session=db_session,
        passwords=fast_passwords,
    )

    assert code == EXIT_REJECTED
    assert "ya existe" in capsys.readouterr().err
    assert (_count(db_session, User), _count(db_session, AuditLog)) == (users, logs)
    # El SAVEPOINT solo deshizo el intento: lo que ya estaba en la sesión sigue ahí.
    db_session.refresh(existing)
    assert existing.role is UserRole.GUARD


def test_otra_restriccion_no_se_disfraza_de_usuario_repetido(
    db_session: Session, fast_passwords: Passwords
) -> None:
    # Sin pasar por la validación de main, solo el CHECK de la base frena el formato.
    with pytest.raises(IntegrityError, match="ck_users_username_format"):
        create_admin(db_session, fast_passwords, username="a b", full_name="X", password=PASSWORD)
