"""add check constraints for role enums

Revision ID: bfe1bcdb54d3
Revises: ce449cce377c
Create Date: 2026-03-17 19:21:37.678145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfe1bcdb54d3'
down_revision: Union[str, None] = 'ce449cce377c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, normalize users.role to lowercase (it's VARCHAR)
    op.execute("UPDATE users SET role = LOWER(role)")

    # For group_memberships, convert from PostgreSQL ENUM to VARCHAR with CHECK constraint
    # Step 1: Add a temporary column
    op.add_column(
        "group_memberships",
        sa.Column("role_temp", sa.String(length=50), nullable=True),
    )

    # Step 2: Copy data from enum to temp column (cast and normalize)
    op.execute("UPDATE group_memberships SET role_temp = LOWER(role::text)")

    # Step 3: Drop the old enum column
    op.drop_column("group_memberships", "role")

    # Step 4: Rename temp column to role
    op.alter_column("group_memberships", "role_temp", new_column_name="role")

    # Step 5: Make it NOT NULL with default 'user'
    op.alter_column(
        "group_memberships",
        "role",
        nullable=False,
        server_default="user",
    )

    # Step 6: Add index back (it was on the enum column)
    op.create_index("ix_group_memberships_role", "group_memberships", ["role"])

    # Add CHECK constraint for users.role to enforce UserRole enum values
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin', 'user')",
    )

    # Add CHECK constraint for group_memberships.role to enforce MemberRole enum values
    op.create_check_constraint(
        "ck_group_memberships_role",
        "group_memberships",
        "role IN ('admin', 'user')",
    )

    # Drop the now-unused PostgreSQL ENUM type
    op.execute("DROP TYPE IF EXISTS memberrole")


def downgrade() -> None:
    # Recreate the ENUM type
    op.execute("CREATE TYPE memberrole AS ENUM ('ADMIN', 'USER')")

    # Remove CHECK constraints
    op.drop_constraint("ck_group_memberships_role", "group_memberships", type_="check")
    op.drop_constraint("ck_users_role", "users", type_="check")

    # Drop index
    op.drop_index("ix_group_memberships_role", table_name="group_memberships")

    # Convert group_memberships.role back to ENUM
    op.add_column(
        "group_memberships",
        sa.Column("role_temp", sa.Enum("ADMIN", "USER", name="memberrole"), nullable=True),
    )
    op.execute("UPDATE group_memberships SET role_temp = UPPER(role)::memberrole")
    op.drop_column("group_memberships", "role")
    op.alter_column("group_memberships", "role_temp", new_column_name="role")
    op.alter_column("group_memberships", "role", nullable=False)
    op.create_index("ix_group_memberships_role", "group_memberships", ["role"])

    # Convert users.role back to uppercase
    op.execute("UPDATE users SET role = UPPER(role)")
