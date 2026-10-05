"""Contrato `PlateRead`: una lectura de placa producida en la portería."""

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
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


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


class PlateRead(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        json_schema_serialization_defaults_required=True,
    )

    # strict on str fields: in lax mode pydantic would decode bytes into str.
    schema_version: Literal[1] = 1
    event_id: uuid.UUID = Field(default_factory=new_event_id)
    plate: str = Field(strict=True)
    raw_text: str = Field(strict=True)
    plate_kind: PlateKind = PlateKind.UNKNOWN
    # strict float still accepts int (0, 1) but rejects bool and numeric strings.
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False, strict=True)
    captured_at: AwareDatetime
    lane_id: str = Field(min_length=1, strict=True)
    source: Source
    photo: str | None = Field(default=None, min_length=1, strict=True)

    @model_validator(mode="before")
    @classmethod
    def derive_plate_kind(cls, data: Any) -> Any:
        if not isinstance(data, Mapping) or not isinstance(data.get("plate"), str):
            return data
        derived = classify_plate(normalize_plate(data["plate"]))
        if data.get("plate_kind", derived) != derived:
            raise ValueError("plate_kind does not match plate")
        return {**data, "plate_kind": derived}

    # Literal[1] does not support strict and would accept True and 1.0.
    @field_validator("schema_version", mode="before")
    @classmethod
    def require_int_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @field_validator("plate")
    @classmethod
    def normalize(cls, value: str) -> str:
        plate = normalize_plate(value)
        if not plate:
            raise ValueError("plate is empty after normalization")
        return plate

    @field_validator("raw_text", "lane_id", "photo")
    @classmethod
    def reject_blank(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is not None and not value.strip():
            raise ValueError(f"{info.field_name} is blank")
        return value

    @field_validator("event_id")
    @classmethod
    def require_uuid7(cls, value: uuid.UUID) -> uuid.UUID:
        if value.version != UUID_VERSION:
            raise ValueError("event_id must be a UUID version 7")
        return value

    # strict on captured_at would also reject ISO strings in Python mode, so
    # Unix timestamps (numbers or numeric strings) and bytes are rejected here.
    @field_validator("captured_at", mode="before")
    @classmethod
    def reject_timestamp(cls, value: object) -> object:
        if isinstance(value, datetime) or (isinstance(value, str) and not _is_number(value)):
            return value
        raise ValueError("captured_at must be an ISO 8601 date-time")

    @field_validator("captured_at")
    @classmethod
    def to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
