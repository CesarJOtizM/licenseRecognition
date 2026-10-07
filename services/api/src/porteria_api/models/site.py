"""Topología del conjunto: torres y unidades; porterías, carriles, cámaras y talanqueras."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from porteria_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from porteria_api.models.enums import CameraKind, LaneDirection, enum_type


class Tower(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "towers"

    name: Mapped[str] = mapped_column(String(100), unique=True)


class Unit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Apartamento o casa. El único (tower_id, number) también sirve de índice para la FK."""

    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("tower_id", "number"),)

    tower_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("towers.id", ondelete="RESTRICT"))
    number: Mapped[str] = mapped_column(String(20))


class Gatehouse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Portería. No depende de una torre: una portería atiende a todo el conjunto."""

    __tablename__ = "gatehouses"

    name: Mapped[str] = mapped_column(String(100), unique=True)


class Lane(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Carril. `code` es el `lane_id` que el equipo local pone en cada `PlateRead`."""

    __tablename__ = "lanes"
    __table_args__ = (CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),)

    gatehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gatehouses.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    direction: Mapped[LaneDirection] = mapped_column(enum_type(LaneDirection, "direction"))


class Camera(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cameras"

    lane_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lanes.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[CameraKind] = mapped_column(enum_type(CameraKind, "kind"))


class Gate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Talanquera. Una por carril; el único de `lane_id` también sirve de índice para la FK."""

    __tablename__ = "gates"

    lane_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lanes.id", ondelete="RESTRICT"), unique=True
    )
    name: Mapped[str] = mapped_column(String(100))
