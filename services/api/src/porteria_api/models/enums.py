"""Valores fijos que se guardan como texto con un CHECK, no como tipo ENUM de PostgreSQL."""

import enum

from sqlalchemy import Enum

# Largo fijo: agregar un valor nuevo solo cambia el CHECK, no el tipo de la columna.
ENUM_LENGTH = 20


class LaneDirection(enum.StrEnum):
    ENTRY = "entry"
    EXIT = "exit"


class CameraKind(enum.StrEnum):
    IP = "ip"
    LPR = "lpr"


def _values(enum_cls: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_cls]


def enum_type(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Columna que guarda `member.value` ('entry'), no el nombre ('ENTRY').

    `name` nombra el CHECK: con la convención queda `ck_<tabla>_<name>`.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=_values,
        length=ENUM_LENGTH,
    )
