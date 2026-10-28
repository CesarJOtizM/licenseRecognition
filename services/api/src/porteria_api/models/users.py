"""Usuarios que entran a la API: administradores, guardas y residentes."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from porteria_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from porteria_api.models.enums import UserRole, UserStatus, enum_type
from porteria_api.models.people import Resident

USERNAME_PATTERN = "^[a-z0-9][a-z0-9._-]{2,49}$"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """`token_version` va dentro de cada token: subirlo invalida los tokens ya emitidos."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"username ~ '{USERNAME_PATTERN}'", name="username_format"),
        CheckConstraint("(role = 'resident') = (resident_id IS NOT NULL)", name="resident_link"),
    )

    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole, "role"))
    status: Mapped[UserStatus] = mapped_column(
        enum_type(UserStatus, "status"), default=UserStatus.ACTIVE
    )
    # El único de `resident_id` también sirve de índice para la FK.
    resident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("residents.id", ondelete="RESTRICT"), unique=True
    )
    token_version: Mapped[int] = mapped_column(server_default=text("0"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    resident: Mapped[Resident | None] = relationship()

    @validates("username")
    def _normalize_username(self, _key: str, username: str) -> str:
        return username.strip().lower()
