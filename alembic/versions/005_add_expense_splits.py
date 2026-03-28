"""Add expense_splits table for Epic 4 split modes.

Revision ID: 005
Revises: 004
Create Date: 2026-03-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create expense_splits table for storing calculated split amounts
    op.create_table(
        "expense_splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "amount",
            sa.Numeric(precision=19, scale=2),
            nullable=False,
        ),
        sa.Column(
            "share_value",
            sa.Numeric(precision=19, scale=4),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("expense_id", "user_id", name="uq_expense_user"),
    )
    op.create_index("ix_expense_splits_expense_id", "expense_splits", ["expense_id"])
    op.create_index("ix_expense_splits_user_id", "expense_splits", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_expense_splits_user_id", table_name="expense_splits")
    op.drop_index("ix_expense_splits_expense_id", table_name="expense_splits")
    op.drop_table("expense_splits")
