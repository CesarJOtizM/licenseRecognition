from porteria_api.models import Base
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    Uuid,
    create_engine,
)
from sqlalchemy.schema import CreateIndex, CreateTable

# Crear el motor no abre conexiones; solo se usa su dialecto para generar el DDL.
POSTGRESQL = create_engine("postgresql+psycopg://").dialect


def _ddl(element: CreateTable | CreateIndex) -> str:
    return str(element.compile(dialect=POSTGRESQL))


def test_las_restricciones_toman_el_nombre_de_la_convencion() -> None:
    # MetaData aparte con la misma convención: no ensucia Base.metadata (prueba de drift).
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    Table("towers", metadata, Column("id", Uuid, primary_key=True))
    units = Table(
        "units",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("tower_id", ForeignKey("towers.id"), nullable=False, index=True),
        Column("number", String(20), nullable=False, unique=True),
        CheckConstraint("length(number) > 0", name="number_not_blank"),
    )

    ddl = _ddl(CreateTable(units))
    (index,) = units.indexes

    assert "CONSTRAINT pk_units PRIMARY KEY" in ddl
    assert "CONSTRAINT fk_units_tower_id_towers FOREIGN KEY" in ddl
    assert "CONSTRAINT uq_units_number UNIQUE" in ddl
    assert "CONSTRAINT ck_units_number_not_blank CHECK" in ddl
    assert _ddl(CreateIndex(index)).startswith("CREATE INDEX ix_units_tower_id ")


def test_unique_de_varias_columnas_incluye_todas_en_el_nombre() -> None:
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    units = Table(
        "units",
        metadata,
        Column("tower_id", Uuid),
        Column("number", String(20)),
        UniqueConstraint("tower_id", "number"),
    )

    assert "CONSTRAINT uq_units_tower_id_number UNIQUE" in _ddl(CreateTable(units))
