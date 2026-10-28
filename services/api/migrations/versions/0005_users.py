"""users: usuarios con rol, estado y vínculo opcional con un residente.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-28 15:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Los enums van como VARCHAR + CHECK escrito aquí: autogenerate duplicaba el CHECK.
    op.create_table(
        "users",
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
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resident_id", sa.Uuid(), nullable=True),
        sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "username ~ '^[a-z0-9][a-z0-9._-]{2,49}$'", name=op.f("ck_users_username_format")
        ),
        sa.CheckConstraint("role IN ('admin', 'guard', 'resident')", name=op.f("ck_users_role")),
        sa.CheckConstraint("status IN ('active', 'disabled')", name=op.f("ck_users_status")),
        sa.CheckConstraint(
            "(role = 'resident') = (resident_id IS NOT NULL)",
            name=op.f("ck_users_resident_link"),
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"],
            ["residents.id"],
            name=op.f("fk_users_resident_id_residents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("resident_id", name=op.f("uq_users_resident_id")),
        sa.UniqueConstraint("username", name=op.f("uq_users_username")),
    )


def downgrade() -> None:
    op.drop_table("users")
