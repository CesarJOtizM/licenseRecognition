"""Dependencias de FastAPI: quién hace la petición (`CurrentUser`) y si su rol puede pasar."""

from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from porteria_api.config import Settings
from porteria_api.db import SessionDep
from porteria_api.models import ResidentStatus, User, UserRole, UserStatus
from porteria_api.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def is_login_allowed(user: User) -> bool:
    """Un usuario deshabilitado, o un residente cuyo residente está inactivo, no entra."""
    if user.status is not UserStatus.ACTIVE:
        return False
    if user.role is UserRole.RESIDENT:
        return user.resident is not None and user.resident.status is ResidentStatus.ACTIVE
    return True


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    # El token va primero: sin token se responde 401 antes de abrir la sesión.
    token: Annotated[str, Depends(oauth2_scheme)],
    request: Request,
    session: SessionDep,
) -> User:
    """Rol, estado y `token_version` salen de la base, no del token: un cambio aplica ya."""
    settings: Settings = request.app.state.settings
    try:
        claims = decode_access_token(
            token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
    except jwt.InvalidTokenError:
        raise _credentials_error() from None
    user = session.get(User, claims.user_id)
    if user is None or user.token_version != claims.token_version or not is_login_allowed(user):
        raise _credentials_error()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Dependencia que responde 403 si el usuario actual no tiene uno de `roles`."""

    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
            )
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
