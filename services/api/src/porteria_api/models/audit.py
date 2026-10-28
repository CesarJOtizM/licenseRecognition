"""Bitácora de auditoría: quién cambió qué y cuándo. Solo se agregan filas."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from porteria_api.models.base import Base, UUIDPrimaryKeyMixin

ACTION_PATTERN = r"^[a-z_]+\.[a-z_]+$"

type JSONScalar = str | int | bool | None


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Sin `updated_at` (ADR 0007): un trigger de la base rechaza UPDATE, DELETE y TRUNCATE."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(f"action ~ '{ACTION_PATTERN}'", name="action_format"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # NULL cuando el cambio no lo hizo un usuario (por ejemplo, el comando create-admin).
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    action: Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None]
    before: Mapped[dict[str, JSONScalar] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, JSONScalar] | None] = mapped_column(JSONB)
