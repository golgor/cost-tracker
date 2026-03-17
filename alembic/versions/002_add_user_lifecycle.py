"""add user lifecycle and role management

Revision ID: 002
Revises: 001
Create Date: 2026-03-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add user lifecycle and role columns
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=50), nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "users",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "deactivated_by_user_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Add foreign key constraint for deactivated_by_user_id
    op.create_foreign_key(
        "users_deactivated_by_user_id_fkey",
        "users",
        "users",
        ["deactivated_by_user_id"],
        ["id"],
    )

    # Add CHECK constraint for role
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin', 'user')",
    )

    # Add indexes
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_deactivated_at", "users", ["deactivated_at"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_users_deactivated_at", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_role", table_name="users")

    # Drop CHECK constraint
    op.drop_constraint("ck_users_role", "users", type_="check")

    # Drop foreign key
    op.drop_constraint("users_deactivated_by_user_id_fkey", "users", type_="foreignkey")

    # Drop columns
    op.drop_column("users", "deactivated_by_user_id")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
