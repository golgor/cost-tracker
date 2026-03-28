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
    # Add user role column
    op.add_column(
        "users",
        sa.Column(
            "role", sa.Enum("ADMIN", "USER", name="roletype"), nullable=False, server_default="USER"
        ),
    )

    # Add indexes
    op.create_index("ix_users_role", "users", ["role"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_users_role", table_name="users")

    # Drop columns
    op.drop_column("users", "role")

    # Note: roletype ENUM is not dropped here - it's shared with 001_initial_schema.py
    # and will be dropped there when group_memberships table is dropped
