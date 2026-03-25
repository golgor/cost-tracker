"""add expenses table

Revision ID: 003
Revises: 002
Create Date: 2026-03-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Expenses table - reuse existing splittype ENUM, create new expensestatus ENUM
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(length=3), nullable=False),
        sa.Column(
            "split_type",
            postgresql.ENUM("EVEN", name="splittype", create_type=False),
            nullable=False,
            server_default="EVEN",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING", "ACCEPTED", "GIFT", "SETTLED", name="expensestatus", create_type=True
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expenses_group_id_date", "expenses", ["group_id", "date"])
    op.create_index("ix_expenses_group_id", "expenses", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_expenses_group_id", table_name="expenses")
    op.drop_index("ix_expenses_group_id_date", table_name="expenses")
    op.drop_table("expenses")
    # Drop ENUM type (must be after table is dropped)
    op.execute("DROP TYPE IF EXISTS expensestatus")
