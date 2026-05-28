"""baseline schema

Captures the drift between the live SQLite tables (created originally by
Base.metadata.create_all()) and the current SQLAlchemy models. The only
real difference at the point of Alembic introduction is the Phase-1
BIZ-01 work that added ondelete="CASCADE" to the five child tables that
reference cases.case_id. Existing prod/dev SQLite databases were created
before that change, so their FK definitions don't carry the CASCADE
clause; the model definitions do.

Operator workflow:
  * For existing deployments (dev + prod SQLite): run
    `alembic stamp 0001` so the version is recorded without re-applying
    DDL. Data is preserved exactly. The schema drift documented here
    will be closed naturally when Phase 3 migrates to Postgres, where a
    fresh "create everything" migration will replace this baseline.
  * For a brand-new SQLite (rare; tests use create_all directly and
    bypass Alembic via ALEMBIC_BOOTSTRAP=skip): the baseline assumes
    the tables already exist, so create_all should be run once before
    `alembic stamp 0001`.

Revision ID: 0001
Revises:
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOTE: `alembic check` will report drift on databases stamped with this
    # baseline. That is by design — see this module's docstring above.
    # Operators stamping pre-Alembic deployments must use
    #   alembic stamp 0001
    # rather than `alembic upgrade head`; the latter would attempt these
    # ALTERs against tables that were created via SQLAlchemy create_all.
    # Phase 3's Postgres cutover replaces this baseline with a fresh
    # create-everything revision.
    with op.batch_alter_table("case_diagrams", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            None, "cases", ["case_id"], ["case_id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("client_profiles", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            None, "cases", ["case_id"], ["case_id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            None, "cases", ["case_id"], ["case_id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            None, "cases", ["case_id"], ["case_id"], ondelete="CASCADE"
        )

    with op.batch_alter_table("recommendations", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            None, "cases", ["case_id"], ["case_id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("recommendations", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(None, "cases", ["case_id"], ["case_id"])

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(None, "cases", ["case_id"], ["case_id"])

    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(None, "cases", ["case_id"], ["case_id"])

    with op.batch_alter_table("client_profiles", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(None, "cases", ["case_id"], ["case_id"])

    with op.batch_alter_table("case_diagrams", schema=None) as batch_op:
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(None, "cases", ["case_id"], ["case_id"])
