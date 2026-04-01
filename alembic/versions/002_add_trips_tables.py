"""add trips tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. guests (global address book) ──────────────────────────────
    op.create_table(
        "guests",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 2. trips ─────────────────────────────────────────────────────
    op.create_table(
        "trips",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(length=3), nullable=False),
        sa.Column(
            "sharing_token",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trips_sharing_token", "trips", ["sharing_token"], unique=True)

    # ── 3. trip_participants (many-to-many) ──────────────────────────
    op.create_table(
        "trip_participants",
        sa.Column("trip_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guest_id"], ["guests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trip_id", "guest_id"),
    )

    # ── 4. trip_expenses ─────────────────────────────────────────────
    op.create_table(
        "trip_expenses",
        sa.Column("trip_id", sa.Integer(), nullable=False),
        sa.Column(
            "description",
            sqlmodel.sql.sqltypes.AutoString(length=255),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("paid_by_id", sa.Integer(), nullable=False),
        sa.Column("created_by_guest_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
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
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paid_by_id"], ["guests.id"]),
        sa.ForeignKeyConstraint(["created_by_guest_id"], ["guests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trip_expenses_date", "trip_expenses", ["date"])

    # ── 5. trip_expense_splits ───────────────────────────────────────
    op.create_table(
        "trip_expense_splits",
        sa.Column("trip_expense_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column("share_value", sa.Numeric(precision=19, scale=4), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["trip_expense_id"], ["trip_expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guest_id"], ["guests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_expense_id", "guest_id", name="uq_trip_expense_guest"),
    )
    op.create_index(
        "ix_trip_expense_splits_trip_expense_id",
        "trip_expense_splits",
        ["trip_expense_id"],
    )
    op.create_index("ix_trip_expense_splits_guest_id", "trip_expense_splits", ["guest_id"])

    # ── 6. trip_expense_notes ────────────────────────────────────────
    op.create_table(
        "trip_expense_notes",
        sa.Column("trip_expense_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["trip_expense_id"], ["trip_expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["guests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trip_expense_notes_trip_expense_id",
        "trip_expense_notes",
        ["trip_expense_id"],
    )
    op.create_index("ix_trip_expense_notes_author_id", "trip_expense_notes", ["author_id"])
    op.create_index(
        "ix_trip_expense_notes_expense_id_created_at",
        "trip_expense_notes",
        ["trip_expense_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("trip_expense_notes")
    op.drop_table("trip_expense_splits")
    op.drop_index("ix_trip_expenses_date", table_name="trip_expenses")
    op.drop_table("trip_expenses")
    op.drop_table("trip_participants")
    op.drop_index("ix_trips_sharing_token", table_name="trips")
    op.drop_table("trips")
    op.drop_table("guests")
