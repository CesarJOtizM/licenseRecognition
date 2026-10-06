"""Contratos de eventos compartidos entre los servicios."""

from lr_contracts.plate_read import PlateRead, Source, new_event_id
from lr_contracts.plates import PlateKind, classify_plate, normalize_plate

__version__ = "0.1.0"

__all__ = [
    "PlateKind",
    "PlateRead",
    "Source",
    "__version__",
    "classify_plate",
    "new_event_id",
    "normalize_plate",
]
