"""add recurring expense fields

Revision ID: 008
Revises: 007
Create Date: 2026-03-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("recurring_definition_id", sa.Integer(), nullable=True))
    op.add_column("expenses", sa.Column("billing_period", sa.String(length=10), nullable=True))
    op.add_column(
        "expenses",
        sa.Column(
            "is_auto_generated",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )

    op.create_foreign_key(
        "fk_expenses_recurring_definition_id",
        "expenses",
        "recurring_definitions",
        ["recurring_definition_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Partial unique index: one expense per (definition, billing_period)
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_expenses_definition_billing_period "
            "ON expenses (recurring_definition_id, billing_period) "
            "WHERE recurring_definition_id IS NOT NULL"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_expenses_definition_billing_period"))
    op.drop_constraint("fk_expenses_recurring_definition_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "is_auto_generated")
    op.drop_column("expenses", "billing_period")
    op.drop_column("expenses", "recurring_definition_id")
