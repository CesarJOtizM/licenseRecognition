"""site topology: torres, unidades, porterías, carriles, cámaras y talanqueras.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07 15:27:10.440248
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
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
    op.create_table(
        "towers",
        *_base_columns(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_towers")),
        sa.UniqueConstraint("name", name=op.f("uq_towers_name")),
    )
    op.create_table(
        "units",
        *_base_columns(),
        sa.Column("tower_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["tower_id"],
            ["towers.id"],
            name=op.f("fk_units_tower_id_towers"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_units")),
        sa.UniqueConstraint("tower_id", "number", name=op.f("uq_units_tower_id_number")),
    )
    op.create_table(
        "gatehouses",
        *_base_columns(),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gatehouses")),
        sa.UniqueConstraint("name", name=op.f("uq_gatehouses_name")),
    )
    # Los enums van como VARCHAR + CHECK escrito aquí: autogenerate duplicaba el CHECK.
    op.create_table(
        "lanes",
        *_base_columns(),
        sa.Column("gatehouse_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.CheckConstraint("direction IN ('entry', 'exit')", name=op.f("ck_lanes_direction")),
        sa.CheckConstraint("length(btrim(code)) > 0", name=op.f("ck_lanes_code_not_blank")),
        sa.ForeignKeyConstraint(
            ["gatehouse_id"],
            ["gatehouses.id"],
            name=op.f("fk_lanes_gatehouse_id_gatehouses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lanes")),
        sa.UniqueConstraint("code", name=op.f("uq_lanes_code")),
    )
    op.create_index(op.f("ix_lanes_gatehouse_id"), "lanes", ["gatehouse_id"], unique=False)
    op.create_table(
        "cameras",
        *_base_columns(),
        sa.Column("lane_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.CheckConstraint("kind IN ('ip', 'lpr')", name=op.f("ck_cameras_kind")),
        sa.ForeignKeyConstraint(
            ["lane_id"], ["lanes.id"], name=op.f("fk_cameras_lane_id_lanes"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cameras")),
    )
    op.create_index(op.f("ix_cameras_lane_id"), "cameras", ["lane_id"], unique=False)
    op.create_table(
        "gates",
        *_base_columns(),
        sa.Column("lane_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["lane_id"], ["lanes.id"], name=op.f("fk_gates_lane_id_lanes"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gates")),
        sa.UniqueConstraint("lane_id", name=op.f("uq_gates_lane_id")),
    )


def downgrade() -> None:
    # Orden inverso: primero los hijos, para no chocar con las FK RESTRICT.
    op.drop_table("gates")
    op.drop_index(op.f("ix_cameras_lane_id"), table_name="cameras")
    op.drop_table("cameras")
    op.drop_index(op.f("ix_lanes_gatehouse_id"), table_name="lanes")
    op.drop_table("lanes")
    op.drop_table("gatehouses")
    op.drop_table("units")
    op.drop_table("towers")
