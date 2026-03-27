"""add recurring definitions

Revision ID: 007
Revises: 006
Create Date: 2026-03-27 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create recurringfrequency enum type
    recurringfrequency_enum = postgresql.ENUM(
        "MONTHLY",
        "QUARTERLY",
        "SEMI_ANNUALLY",
        "YEARLY",
        "EVERY_N_MONTHS",
        name="recurringfrequency",
    )
    recurringfrequency_enum.create(op.get_bind())

    op.create_table(
        "recurring_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column(
            "frequency",
            postgresql.ENUM(
                "MONTHLY",
                "QUARTERLY",
                "SEMI_ANNUALLY",
                "YEARLY",
                "EVERY_N_MONTHS",
                name="recurringfrequency",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("interval_months", sa.Integer(), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column(
            "split_type",
            postgresql.ENUM(
                "EVEN",
                "SHARES",
                "PERCENTAGE",
                "EXACT",
                name="splittype",
                create_type=False,
            ),
            nullable=False,
            server_default="EVEN",
        ),
        sa.Column("split_config", sa.JSON(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("auto_generate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "deleted_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["groups.id"],
            name=op.f("recurring_definitions_group_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["payer_id"],
            ["users.id"],
            name=op.f("recurring_definitions_payer_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("recurring_definitions_pkey")),
    )
    op.create_index(
        "ix_recurring_definitions_group_id",
        "recurring_definitions",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        "ix_recurring_definitions_next_due_date",
        "recurring_definitions",
        ["next_due_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_recurring_definitions_next_due_date", table_name="recurring_definitions")
    op.drop_index("ix_recurring_definitions_group_id", table_name="recurring_definitions")
    op.drop_table("recurring_definitions")

    recurringfrequency_enum = postgresql.ENUM(name="recurringfrequency")
    recurringfrequency_enum.drop(op.get_bind())
