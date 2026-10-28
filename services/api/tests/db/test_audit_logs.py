"""Bitácora de auditoría: formato de la acción, actor y filas que no se pueden cambiar."""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session
from uuid_utils.compat import uuid7

pytestmark = pytest.mark.db

INSERT_LOG = (
    "INSERT INTO audit_logs (id, actor_user_id, action, entity_type)"
    " VALUES (:id, :actor_user_id, :action, 'user')"
)
FUNCTION_EXISTS = "SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'audit_logs_append_only')"


@contextmanager
def _violates(constraint: str) -> Iterator[None]:
    with pytest.raises(IntegrityError) as exc_info:
        yield
    orig = exc_info.value.orig
    assert isinstance(orig, psycopg.Error)
    assert orig.diag.constraint_name == constraint


def _insert_log(
    session: Session, *, action: str = "user.created", actor: UUID | None = None
) -> UUID:
    log_id = uuid7()
    session.execute(text(INSERT_LOG), {"id": log_id, "actor_user_id": actor, "action": action})
    return log_id


def test_una_fila_nueva_toma_la_fecha_de_la_base(db_session: Session) -> None:
    log_id = _insert_log(db_session)

    stored = db_session.execute(
        text("SELECT occurred_at = now(), before, after FROM audit_logs WHERE id = :id"),
        {"id": log_id},
    ).one()

    assert tuple(stored) == (True, None, None)


@pytest.mark.parametrize("action", ["User.Created", "user", "user.created.again", "user created"])
def test_una_accion_sin_formato_entidad_punto_verbo_viola_el_check(
    db_session: Session, action: str
) -> None:
    with _violates("ck_audit_logs_action_format"):
        _insert_log(db_session, action=action)


def test_un_actor_inexistente_viola_la_fk(db_session: Session) -> None:
    with _violates("fk_audit_logs_actor_user_id_users"):
        _insert_log(db_session, actor=uuid7())


@pytest.mark.parametrize(
    ("operation", "statement"),
    [
        ("UPDATE", "UPDATE audit_logs SET action = 'user.updated' WHERE id = :id"),
        ("DELETE", "DELETE FROM audit_logs WHERE id = :id"),
        ("TRUNCATE", "TRUNCATE audit_logs"),
    ],
)
def test_la_bitacora_no_se_puede_modificar_ni_borrar(
    db_session: Session, operation: str, statement: str
) -> None:
    log_id = _insert_log(db_session)

    # RAISE EXCEPTION llega como SQLSTATE P0001; SQLAlchemy lo envuelve en ProgrammingError.
    with pytest.raises(ProgrammingError) as exc_info, db_session.begin_nested():
        db_session.execute(text(statement), {"id": log_id})

    orig = exc_info.value.orig
    assert isinstance(orig, psycopg.errors.RaiseException)
    assert orig.sqlstate == "P0001"
    assert f"{operation} is not allowed" in str(orig)
    action = db_session.scalar(text("SELECT action FROM audit_logs WHERE id = :id"), {"id": log_id})
    assert action == "user.created"


def test_los_triggers_de_solo_agregar_estan_en_la_tabla(db_session: Session) -> None:
    names = db_session.scalars(
        text(
            "SELECT tgname FROM pg_trigger"
            " WHERE tgrelid = 'audit_logs'::regclass AND NOT tgisinternal"
        )
    )

    assert set(names) == {"audit_logs_no_update_delete", "audit_logs_no_truncate"}


def _function_exists(engine: Engine) -> bool:
    with engine.connect() as connection:
        return bool(connection.scalar(text(FUNCTION_EXISTS)))


def test_bajar_a_0005_borra_la_funcion_del_trigger(
    alembic_config: Config, db_engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")
    assert _function_exists(db_engine)

    command.downgrade(alembic_config, "0005")
    try:
        assert not _function_exists(db_engine)
    finally:
        command.upgrade(alembic_config, "head")
