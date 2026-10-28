"""audit_logs: bitácora de auditoría de solo agregar (trigger contra UPDATE, DELETE y TRUNCATE).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-28 15:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Sin OR REPLACE: si un downgrade deja la función, volver a subir falla (lo detecta el stairway).
CREATE_FUNCTION = """
CREATE FUNCTION audit_logs_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only: % is not allowed', TG_OP;
END
$$
"""
CREATE_ROW_TRIGGER = (
    "CREATE TRIGGER audit_logs_no_update_delete BEFORE UPDATE OR DELETE ON audit_logs"
    " FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only()"
)
# TRUNCATE no pasa por los triggers de fila: necesita uno de sentencia.
CREATE_TRUNCATE_TRIGGER = (
    "CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE ON audit_logs"
    " FOR EACH STATEMENT EXECUTE FUNCTION audit_logs_append_only()"
)


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            r"action ~ '^[a-z_]+\.[a-z_]+$'", name=op.f("ck_audit_logs_action_format")
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(
        op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"], unique=False
    )
    op.create_index(
        "ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"], unique=False
    )
    op.create_index(op.f("ix_audit_logs_occurred_at"), "audit_logs", ["occurred_at"], unique=False)
    op.execute(CREATE_FUNCTION)
    op.execute(CREATE_ROW_TRIGGER)
    op.execute(CREATE_TRUNCATE_TRIGGER)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_occurred_at"), table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_user_id"), table_name="audit_logs")
    # DROP TABLE se lleva los triggers; la función no depende de la tabla y hay que borrarla aparte.
    op.drop_table("audit_logs")
    op.execute("DROP FUNCTION audit_logs_append_only()")
