"""add audit_log table

Creates the audit_log table for SEC-10. Indexes on event_type and
occurred_at support the /admin/audit query patterns (filter-by-event +
descending-time scan).

Note on autogenerate output: when this revision is generated against a
DB stamped at 0001 (rather than upgraded), Alembic also reports the
BIZ-01 ondelete=CASCADE FK swaps as drift. Those belong to the 0001
baseline (whose upgrade body is intentionally never re-applied to
stamped DBs) and are deliberately stripped from this revision — 0002
must do nothing other than create audit_log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("audit_id", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("actor_ip", sa.String(), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=True),
        sa.Column("target_id", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_audit_log_event_type"), ["event_type"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_audit_log_occurred_at"), ["occurred_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_log_occurred_at"))
        batch_op.drop_index(batch_op.f("ix_audit_log_event_type"))
    op.drop_table("audit_log")
