"""vehicle plate_kind check: el tipo de placa no puede contradecir la placa.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07 23:17:29.939647
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        op.f("ck_vehicles_plate_kind_matches_plate"),
        "vehicles",
        "(plate_kind = 'car') = (plate ~ '^[A-Z]{3}[0-9]{3}$')"
        " AND (plate_kind = 'motorcycle') = (plate ~ '^[A-Z]{3}[0-9]{2}[A-Z]$')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_vehicles_plate_kind_matches_plate"), "vehicles", type_="check")
