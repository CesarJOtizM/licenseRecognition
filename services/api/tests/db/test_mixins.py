from datetime import UTC, datetime, timedelta

import pytest
from porteria_api.models import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import MetaData, String, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

pytestmark = pytest.mark.db


class _TestBase(DeclarativeBase):
    # MetaData propia: la tabla de prueba no entra en Base.metadata ni en la prueba de drift.
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)


class Sample(UUIDPrimaryKeyMixin, TimestampMixin, _TestBase):
    __tablename__ = "mixin_samples"

    name: Mapped[str] = mapped_column(String(50))


@pytest.fixture
def session(db_session: Session) -> Session:
    # El CREATE TABLE corre en la transacción de db_session y se deshace con ella.
    _TestBase.metadata.create_all(db_session.connection())
    return db_session


def test_el_id_es_uuid7_y_crece_con_cada_fila(session: Session) -> None:
    first, second = Sample(name="a"), Sample(name="b")
    session.add(first)
    session.flush()
    session.add(second)
    session.flush()

    assert first.id.version == 7
    assert second.id.version == 7
    assert first.id < second.id


def test_las_fechas_las_pone_la_base_con_zona_utc(session: Session) -> None:
    sample = Sample(name="a")
    session.add(sample)
    session.flush()
    session.refresh(sample)

    assert sample.created_at.utcoffset() == timedelta(0)
    assert sample.updated_at.utcoffset() == timedelta(0)


def test_updated_at_cambia_al_modificar_la_fila(session: Session) -> None:
    old = datetime(2000, 1, 1, tzinfo=UTC)
    sample = Sample(name="a")
    session.add(sample)
    session.flush()
    session.execute(update(Sample).where(Sample.id == sample.id).values(updated_at=old))
    session.refresh(sample)
    created_at = sample.created_at

    sample.name = "b"
    session.flush()
    session.refresh(sample)

    assert sample.updated_at > old
    assert sample.created_at == created_at
