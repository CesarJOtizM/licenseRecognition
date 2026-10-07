"""Restricciones de residentes, vehículos y visitantes."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest
from lr_contracts import PlateKind
from porteria_api.models import (
    Base,
    DocumentType,
    Resident,
    Tower,
    Unit,
    Vehicle,
    VehicleStatus,
    Visitor,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid_utils.compat import uuid7

pytestmark = pytest.mark.db


def _add[M: Base](session: Session, row: M) -> M:
    session.add(row)
    session.flush()
    return row


@contextmanager
def _violates(constraint: str) -> Iterator[None]:
    with pytest.raises(IntegrityError) as exc_info:
        yield
    orig = exc_info.value.orig
    assert isinstance(orig, psycopg.Error)
    assert orig.diag.constraint_name == constraint


@pytest.fixture
def unit(db_session: Session) -> Unit:
    tower = _add(db_session, Tower(name="Torre 1"))
    return _add(db_session, Unit(tower_id=tower.id, number="101"))


def _vehicle(unit: Unit, plate: str = "ABC123", status: VehicleStatus | None = None) -> Vehicle:
    vehicle = Vehicle(unit_id=unit.id, plate=plate, plate_kind=PlateKind.CAR)
    if status is not None:
        vehicle.status = status
    return vehicle


def _raw(session: Session, sql: str, **params: object) -> object:
    return session.execute(text(sql), {"id": uuid7(), **params})


def test_residente_vehiculo_y_visitante_se_guardan_con_sus_valores(
    db_session: Session, unit: Unit
) -> None:
    resident = _add(db_session, Resident(unit_id=unit.id, full_name="Ana Gómez"))
    vehicle = _add(db_session, _vehicle(unit))
    visitor = _add(
        db_session,
        Visitor(document_type=DocumentType.CC, document_number="123", full_name="Luis Díaz"),
    )

    stored = db_session.execute(
        text(
            "SELECT r.status, v.status, v.plate_kind, s.document_type, s.photo_path"
            " FROM residents r, vehicles v, visitors s"
            " WHERE r.id = :r AND v.id = :v AND s.id = :s"
        ),
        {"r": resident.id, "v": vehicle.id, "s": visitor.id},
    ).one()

    assert tuple(stored) == ("active", "active", "car", "cc", None)


@pytest.mark.parametrize("typed", ["abc 123", "ABC-123", " abc-123 "])
def test_la_placa_se_guarda_normalizada(db_session: Session, unit: Unit, typed: str) -> None:
    vehicle = _add(db_session, _vehicle(unit, plate=typed))

    raw = db_session.scalar(text("SELECT plate FROM vehicles WHERE id = :id"), {"id": vehicle.id})

    assert raw == "ABC123"


@pytest.mark.parametrize("plate", ["ABC-123", "abc123", "", "AB", "ÁBC123"])
def test_una_placa_sin_normalizar_viola_el_check(
    db_session: Session, unit: Unit, plate: str
) -> None:
    with _violates("ck_vehicles_plate_format"):
        _raw(
            db_session,
            "INSERT INTO vehicles (id, unit_id, plate, plate_kind, status)"
            " VALUES (:id, :unit_id, :plate, 'car', 'active')",
            unit_id=unit.id,
            plate=plate,
        )


def test_una_placa_que_queda_vacia_al_normalizar_viola_el_check(
    db_session: Session, unit: Unit
) -> None:
    with _violates("ck_vehicles_plate_format"):
        _add(db_session, _vehicle(unit, plate=" - "))


@pytest.mark.parametrize("second", [VehicleStatus.ACTIVE, VehicleStatus.BLOCKED])
def test_dos_vehiculos_vigentes_no_comparten_placa(
    db_session: Session, unit: Unit, second: VehicleStatus
) -> None:
    _add(db_session, _vehicle(unit))

    with _violates("uq_vehicles_plate_not_inactive"):
        _add(db_session, _vehicle(unit, status=second))


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (VehicleStatus.INACTIVE, VehicleStatus.ACTIVE),
        (VehicleStatus.INACTIVE, VehicleStatus.INACTIVE),
        (VehicleStatus.ACTIVE, VehicleStatus.INACTIVE),
    ],
)
def test_una_placa_inactiva_no_bloquea_otra_con_la_misma_placa(
    db_session: Session, unit: Unit, first: VehicleStatus, second: VehicleStatus
) -> None:
    _add(db_session, _vehicle(unit, status=first))

    other = _add(db_session, _vehicle(unit, status=second))

    assert other.plate == "ABC123"


@pytest.mark.parametrize(
    ("constraint", "sql"),
    [
        (
            "ck_residents_status",
            "INSERT INTO residents (id, unit_id, full_name, status)"
            " VALUES (:id, :unit_id, 'Ana', 'moved')",
        ),
        (
            "ck_vehicles_status",
            "INSERT INTO vehicles (id, unit_id, plate, plate_kind, status)"
            " VALUES (:id, :unit_id, 'ABC123', 'car', 'stolen')",
        ),
        (
            "ck_vehicles_plate_kind",
            "INSERT INTO vehicles (id, unit_id, plate, plate_kind, status)"
            " VALUES (:id, :unit_id, 'ABC123', 'truck', 'active')",
        ),
        (
            "ck_visitors_document_type",
            "INSERT INTO visitors (id, document_type, document_number, full_name)"
            " VALUES (:id, 'nit', '123', 'Luis')",
        ),
    ],
)
def test_un_valor_fuera_de_la_lista_viola_el_check(
    db_session: Session, unit: Unit, constraint: str, sql: str
) -> None:
    with _violates(constraint):
        _raw(db_session, sql, unit_id=unit.id)


def test_el_documento_del_visitante_es_unico_por_tipo(db_session: Session) -> None:
    def visitor(document_type: DocumentType) -> Visitor:
        return Visitor(document_type=document_type, document_number="123", full_name="Luis")

    _add(db_session, visitor(DocumentType.CC))
    other = _add(db_session, visitor(DocumentType.CE))

    assert other.document_number == "123"
    with _violates("uq_visitors_document_type_document_number"):
        _add(db_session, visitor(DocumentType.CC))


def test_un_residente_con_unidad_inexistente_viola_la_fk(db_session: Session) -> None:
    with _violates("fk_residents_unit_id_units"):
        _add(db_session, Resident(unit_id=uuid7(), full_name="Ana"))


@pytest.mark.parametrize(
    ("child", "constraint"),
    [("resident", "fk_residents_unit_id_units"), ("vehicle", "fk_vehicles_unit_id_units")],
)
def test_no_se_borra_una_unidad_con_residentes_o_vehiculos(
    db_session: Session, unit: Unit, child: str, constraint: str
) -> None:
    row = Resident(unit_id=unit.id, full_name="Ana") if child == "resident" else _vehicle(unit)
    _add(db_session, row)

    with _violates(constraint):
        db_session.delete(unit)
        db_session.flush()


def test_las_fk_son_restrict_y_tienen_indice(db_session: Session) -> None:
    rows = db_session.execute(
        text(
            "SELECT c.conname, c.confdeltype, EXISTS (SELECT 1 FROM pg_index i"
            "  WHERE i.indrelid = c.conrelid AND i.indkey[0] = c.conkey[1])"
            " FROM pg_constraint c"
            " WHERE c.contype = 'f' AND c.conrelid::regclass::text = ANY(:tables)"
        ),
        {"tables": ["residents", "vehicles", "visitors"]},
    )

    assert {name: (kind, indexed) for name, kind, indexed in rows.all()} == {
        "fk_residents_unit_id_units": ("r", True),
        "fk_vehicles_unit_id_units": ("r", True),
    }
