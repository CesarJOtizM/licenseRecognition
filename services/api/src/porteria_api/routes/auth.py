"""POST /auth/login (formulario OAuth2) y GET /auth/me."""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from porteria_api.auth import CurrentUser, is_login_allowed
from porteria_api.config import Settings
from porteria_api.db import SessionDep
from porteria_api.models import User
from porteria_api.schemas import MeResponse, TokenResponse
from porteria_api.security import Passwords, encode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _login_error() -> HTTPException:
    # Un solo mensaje para todo fallo: la respuesta no revela si el usuario existe.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", responses={status.HTTP_401_UNAUTHORIZED: {}})
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    session: SessionDep,
) -> TokenResponse:
    settings: Settings = request.app.state.settings
    passwords: Passwords = request.app.state.passwords
    username = form.username.strip().lower()
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        passwords.verify_dummy(form.password)
        logger.warning("Login fallido para %r: usuario inexistente", username)
        raise _login_error()
    if not passwords.verify(form.password, user.password_hash):
        logger.warning("Login fallido para %r: contraseña incorrecta", username)
        raise _login_error()
    if not is_login_allowed(user):
        logger.warning("Login fallido para %r: usuario no habilitado", username)
        raise _login_error()

    now = datetime.now(UTC)
    user.last_login_at = now
    session.commit()
    logger.info("Login exitoso para %r", username)
    token = encode_access_token(
        user.id,
        user.token_version,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        minutes=settings.access_token_minutes,
        now=now,
    )
    return TokenResponse(access_token=token, expires_in=settings.access_token_minutes * 60)


@router.get("/me")
def me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        resident_id=user.resident_id,
        unit_id=user.resident.unit_id if user.resident else None,
    )
