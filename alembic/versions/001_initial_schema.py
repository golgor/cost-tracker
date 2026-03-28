"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("oidc_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="USER",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by_user_id", sa.Integer(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["deactivated_by_user_id"],
            ["users.id"],
            name="users_deactivated_by_user_id_fkey",
        ),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'USER')",
            name="ck_users_role",
        ),
    )
    op.create_index("ix_users_oidc_sub", "users", ["oidc_sub"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_deactivated_at", "users", ["deactivated_at"])

    # ── 2. groups ─────────────────────────────────────────────────────
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column(
            "default_currency",
            sqlmodel.sql.sqltypes.AutoString(length=3),
            nullable=False,
        ),
        sa.Column(
            "default_split_type",
            sa.String(length=20),
            nullable=False,
            server_default="EVEN",
        ),
        sa.Column(
            "singleton_guard",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "tracking_threshold",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("30"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("singleton_guard", name="uq_groups_singleton_guard"),
        sa.CheckConstraint(
            "default_split_type IN ('EVEN', 'SHARES', 'PERCENTAGE', 'EXACT')",
            name="ck_groups_default_split_type",
        ),
    )

    # ── 3. group_memberships ──────────────────────────────────────────
    op.create_table(
        "group_memberships",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="USER",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "group_id"),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'USER')",
            name="ck_group_memberships_role",
        ),
    )
    op.create_index("ix_group_memberships_role", "group_memberships", ["role"])

    # ── 4. recurring_definitions ──────────────────────────────────────
    op.create_table(
        "recurring_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("interval_months", sa.Integer(), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column(
            "split_type",
            sa.String(length=20),
            nullable=False,
            server_default="EVEN",
        ),
        sa.Column("split_config", sa.JSON(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("auto_generate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "frequency IN ('MONTHLY', 'QUARTERLY', 'SEMI_ANNUALLY', 'YEARLY', 'EVERY_N_MONTHS')",
            name="ck_recurring_definitions_frequency",
        ),
        sa.CheckConstraint(
            "split_type IN ('EVEN', 'SHARES', 'PERCENTAGE', 'EXACT')",
            name="ck_recurring_definitions_split_type",
        ),
    )
    op.create_index(
        "ix_recurring_definitions_group_id",
        "recurring_definitions",
        ["group_id"],
    )
    op.create_index(
        "ix_recurring_definitions_next_due_date",
        "recurring_definitions",
        ["next_due_date"],
    )

    # ── 5. expenses ───────────────────────────────────────────────────
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("payer_id", sa.Integer(), nullable=False),
        sa.Column(
            "currency",
            sqlmodel.sql.sqltypes.AutoString(length=3),
            nullable=False,
        ),
        sa.Column(
            "split_type",
            sa.String(length=20),
            nullable=False,
            server_default="EVEN",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("recurring_definition_id", sa.Integer(), nullable=True),
        sa.Column("billing_period", sa.String(length=10), nullable=True),
        sa.Column(
            "is_auto_generated",
            sa.Boolean(),
            nullable=False,
            server_default="false",
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
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["recurring_definition_id"],
            ["recurring_definitions.id"],
            ondelete="SET NULL",
            name="fk_expenses_recurring_definition_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "split_type IN ('EVEN', 'SHARES', 'PERCENTAGE', 'EXACT')",
            name="ck_expenses_split_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'GIFT', 'SETTLED')",
            name="ck_expenses_status",
        ),
    )
    # F-29: Only the composite index — no redundant single-column ix_expenses_group_id
    op.create_index("ix_expenses_group_id_date", "expenses", ["group_id", "date"])
    # F-19: Missing indexes
    op.create_index("ix_expenses_payer_id", "expenses", ["payer_id"])
    op.create_index("ix_expenses_creator_id", "expenses", ["creator_id"])
    op.create_index("ix_expenses_status", "expenses", ["status"])
    op.create_index(
        "ix_expenses_recurring_definition_id",
        "expenses",
        ["recurring_definition_id"],
    )
    # Partial unique index for billing period deduplication
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX uq_expenses_definition_billing_period "
            "ON expenses (recurring_definition_id, billing_period) "
            "WHERE recurring_definition_id IS NOT NULL"
        )
    )

    # ── 6. expense_splits ─────────────────────────────────────────────
    op.create_table(
        "expense_splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column("share_value", sa.Numeric(precision=19, scale=4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expense_id", "user_id", name="uq_expense_user"),
    )
    op.create_index("ix_expense_splits_expense_id", "expense_splits", ["expense_id"])
    op.create_index("ix_expense_splits_user_id", "expense_splits", ["user_id"])

    # ── 7. expense_notes ──────────────────────────────────────────────
    op.create_table(
        "expense_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_notes_expense_id", "expense_notes", ["expense_id"])
    op.create_index("ix_expense_notes_author_id", "expense_notes", ["author_id"])
    op.create_index(
        "ix_expense_notes_expense_id_created_at",
        "expense_notes",
        ["expense_id", "created_at"],
    )

    # ── 8. settlements ────────────────────────────────────────────────
    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("reference_id", sa.String(length=100), nullable=False),
        sa.Column("settled_by_id", sa.Integer(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["settled_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "reference_id", name="uq_group_reference"),
    )
    op.create_index(
        "ix_settlements_group_id_settled_at",
        "settlements",
        ["group_id", "settled_at"],
    )

    # ── 9. settlement_expenses ────────────────────────────────────────
    # F-21: CASCADE on both FK constraints
    op.create_table(
        "settlement_expenses",
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["settlements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("settlement_id", "expense_id"),
    )

    # ── 10. settlement_transactions ───────────────────────────────────
    op.create_table(
        "settlement_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("settlement_id", sa.Integer(), nullable=False),
        sa.Column("from_user_id", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["settlements.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_settlement_transactions_settlement_id",
        "settlement_transactions",
        ["settlement_id"],
    )


def downgrade() -> None:
    op.drop_table("settlement_transactions")
    op.drop_table("settlement_expenses")
    op.drop_table("settlements")
    op.drop_table("expense_notes")
    op.drop_table("expense_splits")
    op.execute(sa.text("DROP INDEX IF EXISTS uq_expenses_definition_billing_period"))
    op.drop_table("expenses")
    op.drop_table("recurring_definitions")
    op.drop_table("group_memberships")
    op.drop_table("groups")
    op.drop_table("users")
