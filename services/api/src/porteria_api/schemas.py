"""Cuerpos de petición y respuesta de la API (Pydantic)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints, model_validator

from porteria_api.models import UserRole, UserStatus
from porteria_api.models.users import USERNAME_PATTERN
from porteria_api.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH


def _normalize_username(value: str) -> str:
    return value.strip().lower()


# El patrón va en un paso aparte: dentro de un mismo StringConstraints se valida antes de
# pasar a minúsculas, y " Bob " sería rechazado.
Username = Annotated[
    str, AfterValidator(_normalize_username), StringConstraints(pattern=USERNAME_PATTERN)
]
Password = Annotated[
    str, StringConstraints(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int  # segundos


class MeResponse(BaseModel):
    """`resident_id` y `unit_id` son `None` para quien no es residente."""

    id: uuid.UUID
    username: str
    role: UserRole
    resident_id: uuid.UUID | None
    unit_id: uuid.UUID | None


class UserCreate(BaseModel):
    username: Username
    password: Password
    full_name: FullName
    role: UserRole
    resident_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _resident_link(self) -> Self:
        if (self.role is UserRole.RESIDENT) != (self.resident_id is not None):
            raise ValueError("resident_id is required for residents and only for them")
        return self


class UserRead(BaseModel):
    """Sin `password_hash` ni `token_version`: nunca salen de la API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    full_name: str
    role: UserRole
    status: UserStatus
    resident_id: uuid.UUID | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
