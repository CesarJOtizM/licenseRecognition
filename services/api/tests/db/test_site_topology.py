"""Restricciones de torres, unidades, porterías, carriles, cámaras y talanqueras."""

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest
from porteria_api.models import (
    Base,
    Camera,
    CameraKind,
    Gate,
    Gatehouse,
    Lane,
    LaneDirection,
    Tower,
    Unit,
)
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid_utils.compat import uuid7

pytestmark = pytest.mark.db


def _add[M: Base](session: Session, row: M) -> M:
    # El id lo pone Python al hacer flush; sin flush, las FK de los hijos quedarían en None.
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


def _lane(session: Session, code: str = "entrada-1") -> Lane:
    gatehouse = _add(session, Gatehouse(name=f"Portería {code}"))
    lane = Lane(gatehouse_id=gatehouse.id, code=code, name="Entrada", direction=LaneDirection.ENTRY)
    return _add(session, lane)


def test_una_topologia_completa_se_guarda(db_session: Session) -> None:
    tower = _add(db_session, Tower(name="Torre 1"))
    unit = _add(db_session, Unit(tower_id=tower.id, number="101"))
    lane = _lane(db_session)
    camera = _add(db_session, Camera(lane_id=lane.id, name="Cámara 1", kind=CameraKind.LPR))
    gate = _add(db_session, Gate(lane_id=lane.id, name="Talanquera 1"))

    assert unit.tower_id == tower.id
    assert (camera.lane_id, gate.lane_id) == (lane.id, lane.id)


def test_el_nombre_de_la_torre_es_unico(db_session: Session) -> None:
    _add(db_session, Tower(name="Torre 1"))

    with _violates("uq_towers_name"):
        _add(db_session, Tower(name="Torre 1"))


def test_el_nombre_de_la_porteria_es_unico(db_session: Session) -> None:
    _add(db_session, Gatehouse(name="Principal"))

    with _violates("uq_gatehouses_name"):
        _add(db_session, Gatehouse(name="Principal"))


def test_el_numero_de_unidad_no_se_repite_en_la_misma_torre(db_session: Session) -> None:
    tower = _add(db_session, Tower(name="Torre 1"))
    _add(db_session, Unit(tower_id=tower.id, number="101"))

    with _violates("uq_units_tower_id_number"):
        _add(db_session, Unit(tower_id=tower.id, number="101"))


def test_el_mismo_numero_de_unidad_vale_en_torres_distintas(db_session: Session) -> None:
    first, second = _add(db_session, Tower(name="Torre 1")), _add(db_session, Tower(name="Torre 2"))

    units = [_add(db_session, Unit(tower_id=t.id, number="101")) for t in (first, second)]

    assert [u.tower_id for u in units] == [first.id, second.id]


def test_el_codigo_del_carril_es_unico(db_session: Session) -> None:
    _lane(db_session, code="entrada-1")
    gatehouse = _add(db_session, Gatehouse(name="Norte"))

    with _violates("uq_lanes_code"):
        _add(
            db_session,
            Lane(
                gatehouse_id=gatehouse.id,
                code="entrada-1",
                name="Otra",
                direction=LaneDirection.EXIT,
            ),
        )


def test_un_carril_tiene_una_sola_talanquera(db_session: Session) -> None:
    lane = _lane(db_session)
    _add(db_session, Gate(lane_id=lane.id, name="Talanquera 1"))

    with _violates("uq_gates_lane_id"):
        _add(db_session, Gate(lane_id=lane.id, name="Talanquera 2"))


@pytest.mark.parametrize("code", ["", "   "])
def test_el_codigo_del_carril_no_puede_estar_en_blanco(db_session: Session, code: str) -> None:
    gatehouse = _add(db_session, Gatehouse(name="Principal"))

    with _violates("ck_lanes_code_not_blank"):
        _add(
            db_session,
            Lane(gatehouse_id=gatehouse.id, code=code, name="E", direction=LaneDirection.ENTRY),
        )


@pytest.mark.parametrize(
    ("direction", "stored"), [(LaneDirection.ENTRY, "entry"), (LaneDirection.EXIT, "exit")]
)
def test_la_direccion_se_guarda_como_su_valor(
    db_session: Session, direction: LaneDirection, stored: str
) -> None:
    gatehouse = _add(db_session, Gatehouse(name="Principal"))
    lane = _add(
        db_session, Lane(gatehouse_id=gatehouse.id, code="c-1", name="C", direction=direction)
    )

    raw = db_session.scalar(text("SELECT direction FROM lanes WHERE id = :id"), {"id": lane.id})

    assert raw == stored


def test_una_direccion_desconocida_viola_el_check(db_session: Session) -> None:
    gatehouse = _add(db_session, Gatehouse(name="Principal"))

    with _violates("ck_lanes_direction"):
        db_session.execute(
            text(
                "INSERT INTO lanes (id, gatehouse_id, code, name, direction)"
                " VALUES (:id, :gatehouse_id, 'c-1', 'C', 'sideways')"
            ),
            {"id": uuid7(), "gatehouse_id": gatehouse.id},
        )


def test_un_tipo_de_camara_desconocido_viola_el_check(db_session: Session) -> None:
    lane = _lane(db_session)

    with _violates("ck_cameras_kind"):
        db_session.execute(
            text(
                "INSERT INTO cameras (id, lane_id, name, kind)"
                " VALUES (:id, :lane_id, 'C', 'thermal')"
            ),
            {"id": uuid7(), "lane_id": lane.id},
        )


def test_una_camara_con_carril_inexistente_viola_la_fk(db_session: Session) -> None:
    with _violates("fk_cameras_lane_id_lanes"):
        _add(db_session, Camera(lane_id=uuid7(), name="C", kind=CameraKind.IP))


def test_no_se_borra_un_carril_con_camara(db_session: Session) -> None:
    lane = _lane(db_session)
    _add(db_session, Camera(lane_id=lane.id, name="C", kind=CameraKind.IP))

    with _violates("fk_cameras_lane_id_lanes"):
        db_session.delete(lane)
        db_session.flush()


def test_no_se_borra_un_carril_con_talanquera(db_session: Session) -> None:
    lane = _lane(db_session)
    _add(db_session, Gate(lane_id=lane.id, name="T"))

    with _violates("fk_gates_lane_id_lanes"):
        db_session.delete(lane)
        db_session.flush()


def test_no_se_borra_una_torre_con_unidades(db_session: Session) -> None:
    tower = _add(db_session, Tower(name="Torre 1"))
    _add(db_session, Unit(tower_id=tower.id, number="101"))

    with _violates("fk_units_tower_id_towers"):
        db_session.delete(tower)
        db_session.flush()


def test_no_se_borra_una_porteria_con_carriles(db_session: Session) -> None:
    lane = _lane(db_session)
    gatehouse = db_session.get_one(Gatehouse, lane.gatehouse_id)

    with _violates("fk_lanes_gatehouse_id_gatehouses"):
        db_session.delete(gatehouse)
        db_session.flush()


TOPOLOGY_TABLES = ["towers", "units", "gatehouses", "lanes", "cameras", "gates"]


def test_todas_las_fk_son_restrict_y_las_porterias_no_dependen_de_torres(
    db_session: Session,
) -> None:
    rows = db_session.execute(
        text(
            "SELECT conname, confdeltype FROM pg_constraint"
            " WHERE contype = 'f' AND conrelid::regclass::text = ANY(:tables)"
        ),
        {"tables": TOPOLOGY_TABLES},
    )

    # 'r' es RESTRICT; el valor por defecto de PostgreSQL es 'a' (NO ACTION).
    assert dict(rows.all()) == {
        "fk_units_tower_id_towers": "r",
        "fk_lanes_gatehouse_id_gatehouses": "r",
        "fk_cameras_lane_id_lanes": "r",
        "fk_gates_lane_id_lanes": "r",
    }


def _fks_without_index(session: Session) -> list[str]:
    rows = session.scalars(
        text(
            "SELECT c.conname FROM pg_constraint c"
            " WHERE c.contype = 'f' AND c.conrelid::regclass::text = ANY(:tables)"
            " AND NOT EXISTS (SELECT 1 FROM pg_index i"
            "  WHERE i.indrelid = c.conrelid AND i.indkey[0] = c.conkey[1])"
        ),
        {"tables": TOPOLOGY_TABLES},
    )
    return list(rows)


def test_cada_fk_tiene_un_indice_que_empieza_por_su_columna(db_session: Session) -> None:
    assert _fks_without_index(db_session) == []


def test_sin_su_indice_la_fk_aparece_como_no_indexada(db_session: Session) -> None:
    # El DROP corre en la transacción de la prueba y se deshace con ella.
    db_session.execute(text("DROP INDEX ix_cameras_lane_id"))

    assert _fks_without_index(db_session) == ["fk_cameras_lane_id_lanes"]
