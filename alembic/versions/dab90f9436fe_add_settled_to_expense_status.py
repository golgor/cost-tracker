"""add_settled_to_expense_status

Revision ID: dab90f9436fe
Revises: 004
Create Date: 2026-03-25 18:38:17.739595

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "dab90f9436fe"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add SETTLED value to expensestatus enum
    op.execute("ALTER TYPE expensestatus ADD VALUE 'SETTLED'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values
    # This is a one-way migration
    pass
