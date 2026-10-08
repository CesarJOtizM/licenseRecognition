"""people vehicles: residentes, vehículos y visitantes.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07 17:11:49.920896
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    # Los enums van como VARCHAR + CHECK escrito aquí: autogenerate duplicaba el CHECK.
    op.create_table(
        "residents",
        *_base_columns(),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_residents_status")),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["units.id"], name=op.f("fk_residents_unit_id_units"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_residents")),
    )
    op.create_index(op.f("ix_residents_unit_id"), "residents", ["unit_id"], unique=False)
    op.create_table(
        "vehicles",
        *_base_columns(),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("plate", sa.String(length=10), nullable=False),
        sa.Column("plate_kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.CheckConstraint("plate ~ '^[A-Z0-9]{3,10}$'", name=op.f("ck_vehicles_plate_format")),
        sa.CheckConstraint(
            "plate_kind IN ('car', 'motorcycle', 'unknown')", name=op.f("ck_vehicles_plate_kind")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'blocked', 'inactive')", name=op.f("ck_vehicles_status")
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"], ["units.id"], name=op.f("fk_vehicles_unit_id_units"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicles")),
    )
    op.create_index(op.f("ix_vehicles_unit_id"), "vehicles", ["unit_id"], unique=False)
    # Índice único parcial: solo cuenta las filas que cumplen el WHERE.
    op.create_index(
        op.f("uq_vehicles_plate_not_inactive"),
        "vehicles",
        ["plate"],
        unique=True,
        postgresql_where=sa.text("status <> 'inactive'"),
    )
    op.create_table(
        "visitors",
        *_base_columns(),
        sa.Column("document_type", sa.String(length=20), nullable=False),
        sa.Column("document_number", sa.String(length=30), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("photo_path", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "document_type IN ('cc', 'ce', 'passport', 'other')",
            name=op.f("ck_visitors_document_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visitors")),
        sa.UniqueConstraint(
            "document_type",
            "document_number",
            name=op.f("uq_visitors_document_type_document_number"),
        ),
    )


def downgrade() -> None:
    op.drop_table("visitors")
    op.drop_index(op.f("uq_vehicles_plate_not_inactive"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_unit_id"), table_name="vehicles")
    op.drop_table("vehicles")
    op.drop_index(op.f("ix_residents_unit_id"), table_name="residents")
    op.drop_table("residents")
