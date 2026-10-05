"""Contrato `PlateRead`: una lectura de placa producida en la portería."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from uuid_utils.compat import uuid7

from lr_contracts.plates import PlateKind, classify_plate, normalize_plate

UUID_VERSION = 7


class Source(StrEnum):
    PIPELINE = "pipeline"
    LPR_CAMERA = "lpr_camera"


def new_event_id() -> uuid.UUID:
    return uuid7()


class PlateRead(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_serialization_defaults_required=True,
    )

    schema_version: Literal[1] = 1
    event_id: uuid.UUID = Field(default_factory=new_event_id)
    plate: str
    raw_text: str
    plate_kind: PlateKind = PlateKind.UNKNOWN
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    captured_at: AwareDatetime
    lane_id: str = Field(min_length=1)
    source: Source
    # strict: in lax mode pydantic would decode bytes into str.
    photo: str | None = Field(default=None, min_length=1, strict=True)

    @model_validator(mode="before")
    @classmethod
    def derive_plate_kind(cls, data: Any) -> Any:
        if not isinstance(data, dict) or not isinstance(data.get("plate"), str):
            return data
        derived = classify_plate(normalize_plate(data["plate"]))
        if data.get("plate_kind", derived) != derived:
            raise ValueError("plate_kind does not match plate")
        return {**data, "plate_kind": derived}

    @field_validator("plate")
    @classmethod
    def normalize(cls, value: str) -> str:
        plate = normalize_plate(value)
        if not plate:
            raise ValueError("plate is empty after normalization")
        return plate

    @field_validator("raw_text")
    @classmethod
    def reject_blank_raw_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("raw_text is blank")
        return value

    @field_validator("event_id")
    @classmethod
    def require_uuid7(cls, value: uuid.UUID) -> uuid.UUID:
        if value.version != UUID_VERSION:
            raise ValueError("event_id must be a UUID version 7")
        return value

    @field_validator("captured_at")
    @classmethod
    def to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
