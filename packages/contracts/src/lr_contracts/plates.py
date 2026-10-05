"""Normalización y clasificación de placas colombianas."""

import re
from enum import StrEnum

# [0-9] instead of \d: \d also matches non-ASCII digits (for example Arabic-Indic).
_CAR_PATTERN = re.compile(r"[A-Z]{3}[0-9]{3}")
_MOTORCYCLE_PATTERN = re.compile(r"[A-Z]{3}[0-9]{2}[A-Z]")
_SEPARATORS = re.compile(r"[\s-]")


class PlateKind(StrEnum):
    CAR = "car"
    MOTORCYCLE = "motorcycle"
    UNKNOWN = "unknown"


def normalize_plate(text: str) -> str:
    return _SEPARATORS.sub("", text).upper()


def classify_plate(plate: str) -> PlateKind:
    if _CAR_PATTERN.fullmatch(plate):
        return PlateKind.CAR
    if _MOTORCYCLE_PATTERN.fullmatch(plate):
        return PlateKind.MOTORCYCLE
    return PlateKind.UNKNOWN
