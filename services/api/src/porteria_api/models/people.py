"""Personas y vehículos: residentes y vehículos de cada unidad, y visitantes."""

import uuid

from lr_contracts import PlateKind, normalize_plate
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from porteria_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from porteria_api.models.enums import DocumentType, ResidentStatus, VehicleStatus, enum_type

PLATE_LENGTH = 10


class Resident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "residents"

    unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[ResidentStatus] = mapped_column(
        enum_type(ResidentStatus, "status"), default=ResidentStatus.ACTIVE
    )


class Vehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """La placa se guarda como la produce `normalize_plate` (`ABC123`), igual que en `PlateRead`.

    Una placa no puede estar en dos vehículos vigentes; los `inactive` quedan como historia.
    """

    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint(f"plate ~ '^[A-Z0-9]{{3,{PLATE_LENGTH}}}$'", name="plate_format"),
        Index(
            "uq_vehicles_plate_not_inactive",
            "plate",
            unique=True,
            postgresql_where=text("status <> 'inactive'"),
        ),
    )

    unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("units.id", ondelete="RESTRICT"), index=True
    )
    plate: Mapped[str] = mapped_column(String(PLATE_LENGTH))
    plate_kind: Mapped[PlateKind] = mapped_column(enum_type(PlateKind, "plate_kind"))
    status: Mapped[VehicleStatus] = mapped_column(
        enum_type(VehicleStatus, "status"), default=VehicleStatus.ACTIVE
    )

    @validates("plate")
    def _normalize_plate(self, _key: str, plate: str) -> str:
        return normalize_plate(plate)


class Visitor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "visitors"
    __table_args__ = (UniqueConstraint("document_type", "document_number"),)

    document_type: Mapped[DocumentType] = mapped_column(enum_type(DocumentType, "document_type"))
    document_number: Mapped[str] = mapped_column(String(30))
    full_name: Mapped[str] = mapped_column(String(200))
    photo_path: Mapped[str | None] = mapped_column(String(500))
