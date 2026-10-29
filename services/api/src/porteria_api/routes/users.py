"""Gestión de usuarios (solo administradores): alta, listado, edición y cambio de contraseña."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from porteria_api.audit import USER_AUDIT_FIELDS, record_audit, snapshot
from porteria_api.auth import AdminUser
from porteria_api.db import SessionDep
from porteria_api.models import AuditAction, User, UserStatus
from porteria_api.schemas import PasswordReset, UserCreate, UserRead, UserUpdate
from porteria_api.security import Passwords

router = APIRouter(prefix="/users", tags=["users"])

# Se traduce por nombre de restricción: la base decide, sin un SELECT previo que pierda carreras.
CONSTRAINT_ERRORS = {
    "uq_users_username": (status.HTTP_409_CONFLICT, "Username already exists"),
    "uq_users_resident_id": (status.HTTP_409_CONFLICT, "Resident already has a user"),
    "fk_users_resident_id_residents": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Resident does not exist",
    ),
    "ck_users_resident_link": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "resident_id is required for residents and only for them",
    ),
}


def http_error_for(exc: IntegrityError) -> HTTPException | None:
    """La respuesta para una restricción conocida; `None` si es un fallo inesperado."""
    diag = getattr(exc.orig, "diag", None)
    known = CONSTRAINT_ERRORS.get(getattr(diag, "constraint_name", None) or "")
    if known is None:
        return None
    return HTTPException(status_code=known[0], detail=known[1])


@contextmanager
def _savepoint(session: Session) -> Iterator[None]:
    # SAVEPOINT: si la base rechaza el cambio solo se deshace esto, no la transacción entera.
    try:
        with session.begin_nested():
            yield
    except IntegrityError as exc:
        raise http_error_for(exc) or exc from None


def _get_user(session: Session, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate, admin: AdminUser, request: Request, session: SessionDep
) -> UserRead:
    passwords: Passwords = request.app.state.passwords
    user = User(
        username=body.username,
        password_hash=passwords.hash(body.password),
        full_name=body.full_name,
        role=body.role,
        resident_id=body.resident_id,
    )
    with _savepoint(session):
        session.add(user)
    record_audit(
        session,
        actor=admin,
        action=AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=user.id,
        after=snapshot(user, USER_AUDIT_FIELDS),
    )
    session.commit()
    return UserRead.model_validate(user)


@router.get("")
def list_users(_admin: AdminUser, session: SessionDep) -> list[UserRead]:
    users = session.scalars(select(User).order_by(User.username))
    return [UserRead.model_validate(user) for user in users]


@router.patch("/{user_id}")
def update_user(
    user_id: uuid.UUID, body: UserUpdate, admin: AdminUser, session: SessionDep
) -> UserRead:
    user = _get_user(session, user_id)
    sent = body.model_dump(exclude_unset=True)
    changes = {field: value for field, value in sent.items() if getattr(user, field) != value}
    # El admin que actúa siempre queda activo y admin: así nunca se queda el sistema sin admin.
    if user.id == admin.id and changes.keys() & {"role", "status"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot disable or demote your own account",
        )
    if not changes:
        return UserRead.model_validate(user)
    before = snapshot(user, USER_AUDIT_FIELDS)
    with _savepoint(session):
        for field, value in changes.items():
            setattr(user, field, value)
        # Al reactivar, los tokens de antes de deshabilitar siguen sin servir.
        if changes.get("status") is UserStatus.DISABLED:
            user.token_version = User.token_version + 1
    record_audit(
        session,
        actor=admin,
        action=AuditAction.USER_UPDATED,
        entity_type="user",
        entity_id=user.id,
        before=before,
        after=snapshot(user, USER_AUDIT_FIELDS),
    )
    session.commit()
    return UserRead.model_validate(user)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: uuid.UUID,
    body: PasswordReset,
    admin: AdminUser,
    request: Request,
    session: SessionDep,
) -> None:
    user = _get_user(session, user_id)
    passwords: Passwords = request.app.state.passwords
    user.password_hash = passwords.hash(body.new_password)
    user.token_version = User.token_version + 1
    # Sin antes/después: el hecho es la acción; la contraseña nunca llega a la bitácora.
    record_audit(
        session,
        actor=admin,
        action=AuditAction.USER_PASSWORD_RESET,
        entity_type="user",
        entity_id=user.id,
    )
    session.commit()
