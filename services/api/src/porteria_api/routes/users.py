"""Gestión de usuarios (solo administradores): POST /users y GET /users."""

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from porteria_api.audit import USER_AUDIT_FIELDS, record_audit, snapshot
from porteria_api.auth import AdminUser
from porteria_api.db import SessionDep
from porteria_api.models import AuditAction, User
from porteria_api.schemas import UserCreate, UserRead
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


def _insert(session: Session, user: User) -> None:
    # SAVEPOINT: si la base rechaza la fila solo se deshace esto, no la transacción entera.
    try:
        with session.begin_nested():
            session.add(user)
    except IntegrityError as exc:
        raise http_error_for(exc) or exc from None


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
    _insert(session, user)
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
