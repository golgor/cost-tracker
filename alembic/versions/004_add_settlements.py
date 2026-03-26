"""Add settlements table and settlement_expenses join table.

Revision ID: 004
Revises: 003_add_expenses
Create Date: 2025-03-25
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create settlements table (without old transaction columns)
    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=False),
        sa.Column("settled_by_id", sa.Integer(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["settled_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "reference_id", name="uq_group_reference"),
    )
    op.create_index("ix_settlements_group_id_settled_at", "settlements", ["group_id", "settled_at"])

    # Create settlement_expenses join table
    op.create_table(
        "settlement_expenses",
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["settlement_id"], ["settlements.id"]),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"]),
        sa.PrimaryKeyConstraint("settlement_id", "expense_id"),
    )

    # Create settlement_transactions table
    op.create_table(
        "settlement_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["settlements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_settlement_transactions_settlement_id", "settlement_transactions", ["settlement_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_settlement_transactions_settlement_id", table_name="settlement_transactions")
    op.drop_table("settlement_transactions")
    op.drop_table("settlement_expenses")
    op.drop_index("ix_settlements_group_id_settled_at", table_name="settlements")
    op.drop_table("settlements")
