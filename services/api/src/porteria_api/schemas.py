"""Cuerpos de petición y respuesta de la API (Pydantic)."""

import uuid
from typing import Literal

from pydantic import BaseModel

from porteria_api.models import UserRole


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
