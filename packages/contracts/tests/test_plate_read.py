import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from lr_contracts.plate_read import PlateRead, Source, new_event_id
from lr_contracts.plates import PlateKind
from pydantic import ValidationError

UUID7 = "01890a5d-ac96-774b-bcce-b302099a8057"
UUID4 = "9f1c2d3e-4b5a-4c6d-8e7f-0a1b2c3d4e5f"


def test_el_contrato_expone_exactamente_los_campos_acordados() -> None:
    assert set(PlateRead.model_fields) == {
        "schema_version",
        "event_id",
        "plate",
        "raw_text",
        "plate_kind",
        "confidence",
        "captured_at",
        "lane_id",
        "source",
        "photo",
    }


def test_la_version_del_esquema_por_defecto_es_1(payload: dict[str, Any]) -> None:
    assert PlateRead.model_validate(payload).schema_version == 1


def test_una_version_del_esquema_distinta_de_1_se_rechaza(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        PlateRead.model_validate({**payload, "schema_version": 2})


@pytest.mark.parametrize(
    ("plate", "expected"),
    [(" abc-123 ", "ABC123"), ("abc 12d", "ABC12D")],
)
def test_la_placa_se_guarda_normalizada(payload: dict[str, Any], plate: str, expected: str) -> None:
    assert PlateRead.model_validate({**payload, "plate": plate}).plate == expected


@pytest.mark.parametrize("plate", [" - ", ""])
def test_una_placa_vacia_tras_normalizar_se_rechaza(payload: dict[str, Any], plate: str) -> None:
    with pytest.raises(ValidationError, match="plate"):
        PlateRead.model_validate({**payload, "plate": plate})


def test_el_texto_crudo_se_guarda_tal_cual(payload: dict[str, Any]) -> None:
    read = PlateRead.model_validate({**payload, "raw_text": " abc-123 "})
    assert read.raw_text == " abc-123 "


@pytest.mark.parametrize("raw_text", ["  ", ""])
def test_un_texto_crudo_vacio_se_rechaza(payload: dict[str, Any], raw_text: str) -> None:
    with pytest.raises(ValidationError, match="raw_text"):
        PlateRead.model_validate({**payload, "raw_text": raw_text})


@pytest.mark.parametrize(
    ("plate", "expected"),
    [
        ("ABC123", PlateKind.CAR),
        ("abc-12d", PlateKind.MOTORCYCLE),
        ("ABC12", PlateKind.UNKNOWN),
        ("R12345", PlateKind.UNKNOWN),
        ("CD1234", PlateKind.UNKNOWN),
        ("ABCD123", PlateKind.UNKNOWN),
    ],
)
def test_el_tipo_de_placa_se_deriva_de_la_placa_normalizada(
    payload: dict[str, Any], plate: str, expected: PlateKind
) -> None:
    assert PlateRead.model_validate({**payload, "plate": plate}).plate_kind is expected


def test_un_tipo_de_placa_coherente_se_acepta(payload: dict[str, Any]) -> None:
    read = PlateRead.model_validate({**payload, "plate_kind": "car"})
    assert read.plate_kind is PlateKind.CAR


def test_un_tipo_de_placa_que_contradice_la_placa_se_rechaza(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="plate_kind"):
        PlateRead.model_validate({**payload, "plate_kind": "motorcycle"})


def test_derivar_el_tipo_no_modifica_el_diccionario_de_entrada(payload: dict[str, Any]) -> None:
    original = dict(payload)
    PlateRead.model_validate(payload)
    assert payload == original


def test_una_placa_que_no_es_texto_se_rechaza(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="plate"):
        PlateRead.model_validate({**payload, "plate": 123})


@pytest.mark.parametrize("confidence", [0, 0.5, 1])
def test_la_confianza_entre_0_y_1_se_acepta(payload: dict[str, Any], confidence: float) -> None:
    assert PlateRead.model_validate({**payload, "confidence": confidence}).confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, 1.01, math.nan])
def test_la_confianza_fuera_de_rango_o_nan_se_rechaza(
    payload: dict[str, Any], confidence: float
) -> None:
    with pytest.raises(ValidationError, match="confidence"):
        PlateRead.model_validate({**payload, "confidence": confidence})


def test_una_fecha_sin_zona_horaria_se_rechaza(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="captured_at"):
        PlateRead.model_validate({**payload, "captured_at": "2026-10-04T08:00:00"})


def test_una_fecha_con_otra_zona_horaria_se_guarda_en_utc(payload: dict[str, Any]) -> None:
    read = PlateRead.model_validate({**payload, "captured_at": "2026-10-04T08:00:00-05:00"})
    assert read.captured_at == datetime(2026, 10, 4, 13, 0, tzinfo=UTC)
    assert read.captured_at.utcoffset() == timedelta(0)


def test_una_fecha_en_utc_se_guarda_igual(payload: dict[str, Any]) -> None:
    captured_at = datetime(2026, 10, 4, 13, 0, tzinfo=UTC)
    read = PlateRead.model_validate({**payload, "captured_at": captured_at})
    assert read.captured_at == captured_at
    assert read.captured_at.tzinfo is UTC


def test_el_event_id_por_defecto_es_un_uuid7_nuevo(payload: dict[str, Any]) -> None:
    first = PlateRead.model_validate(payload).event_id
    second = PlateRead.model_validate(payload).event_id
    assert type(first) is uuid.UUID
    assert (first.version, second.version) == (7, 7)
    assert first != second


def test_new_event_id_genera_uuid7_de_la_biblioteca_estandar() -> None:
    event_id = new_event_id()
    assert type(event_id) is uuid.UUID
    assert event_id.version == 7


def test_un_event_id_uuid7_inyectado_se_conserva(payload: dict[str, Any]) -> None:
    read = PlateRead.model_validate({**payload, "event_id": UUID7})
    assert read.event_id == uuid.UUID(UUID7)


def test_un_event_id_uuid4_se_rechaza(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="event_id"):
        PlateRead.model_validate({**payload, "event_id": UUID4})


def test_el_origen_lpr_camera_se_acepta(payload: dict[str, Any]) -> None:
    read = PlateRead.model_validate({**payload, "source": "lpr_camera"})
    assert read.source is Source.LPR_CAMERA


def test_un_origen_desconocido_se_rechaza(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="source"):
        PlateRead.model_validate({**payload, "source": "webcam"})


def test_la_foto_es_opcional(payload: dict[str, Any]) -> None:
    assert PlateRead.model_validate(payload).photo is None


def test_la_foto_se_guarda_como_clave_de_texto(payload: dict[str, Any]) -> None:
    read = PlateRead.model_validate({**payload, "photo": "2026/10/04/x.jpg"})
    assert read.photo == "2026/10/04/x.jpg"


@pytest.mark.parametrize("photo", [b"\xff\xd8\xff", b"x.jpg", ""])
def test_una_foto_en_bytes_o_vacia_se_rechaza(payload: dict[str, Any], photo: bytes | str) -> None:
    with pytest.raises(ValidationError, match="photo"):
        PlateRead.model_validate({**payload, "photo": photo})


def test_un_carril_vacio_se_rechaza(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="lane_id"):
        PlateRead.model_validate({**payload, "lane_id": ""})


def test_la_lectura_no_se_puede_modificar(payload: dict[str, Any]) -> None:
    read = PlateRead.model_validate(payload)
    with pytest.raises(ValidationError, match="frozen"):
        read.plate = "XYZ987"  # type: ignore[misc]
    assert read.plate == "ABC123"


def test_un_campo_extra_se_rechaza(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="camera_id"):
        PlateRead.model_validate({**payload, "camera_id": "cam-1"})


@pytest.mark.parametrize("photo", [None, "2026/10/04/x.jpg"])
def test_la_lectura_sobrevive_ida_y_vuelta_por_json(
    payload: dict[str, Any], photo: str | None
) -> None:
    original = PlateRead.model_validate(
        {**payload, "plate": "abc-12d", "captured_at": "2026-10-04T08:00:00-05:00", "photo": photo}
    )
    restored = PlateRead.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.event_id == original.event_id
    assert restored.captured_at == datetime(2026, 10, 4, 13, 0, tzinfo=UTC)
    assert restored.captured_at.utcoffset() == timedelta(0)
    assert restored.plate_kind is PlateKind.MOTORCYCLE
