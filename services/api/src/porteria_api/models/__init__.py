"""Modelos de la base de datos.

Alembic compara contra `Base.metadata`: todo modelo nuevo se importa aquí para que lo vea.
"""

from porteria_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from porteria_api.models.enums import (
    CameraKind,
    DocumentType,
    LaneDirection,
    ResidentStatus,
    UserRole,
    UserStatus,
    VehicleStatus,
)
from porteria_api.models.people import Resident, Vehicle, Visitor
from porteria_api.models.site import Camera, Gate, Gatehouse, Lane, Tower, Unit
from porteria_api.models.users import User

__all__ = [
    "Base",
    "Camera",
    "CameraKind",
    "DocumentType",
    "Gate",
    "Gatehouse",
    "Lane",
    "LaneDirection",
    "Resident",
    "ResidentStatus",
    "TimestampMixin",
    "Tower",
    "UUIDPrimaryKeyMixin",
    "Unit",
    "User",
    "UserRole",
    "UserStatus",
    "Vehicle",
    "VehicleStatus",
    "Visitor",
]
