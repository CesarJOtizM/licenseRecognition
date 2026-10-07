"""Modelos de la base de datos.

Alembic compara contra `Base.metadata`: todo modelo nuevo se importa aquí para que lo vea.
"""

from porteria_api.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from porteria_api.models.enums import CameraKind, LaneDirection
from porteria_api.models.site import Camera, Gate, Gatehouse, Lane, Tower, Unit

__all__ = [
    "Base",
    "Camera",
    "CameraKind",
    "Gate",
    "Gatehouse",
    "Lane",
    "LaneDirection",
    "TimestampMixin",
    "Tower",
    "UUIDPrimaryKeyMixin",
    "Unit",
]
