# Add a Migration

How to create and run Alembic database migrations for Cost Tracker.

## Auto-Generate a Migration

After modifying ORM models in `app/adapters/sqlalchemy/orm_models.py`, generate a migration:

```bash
uv run alembic revision --autogenerate -m "add widgets table"
```

This creates a file like `alembic/versions/009_add_widgets_table.py` with auto-detected changes.
Revision IDs are sequential numbers (001, 002, ...), not UUIDs.

Always **review the generated migration** before running it. Auto-generate catches most changes but
may miss or misinterpret:

- Renamed columns (detected as drop + add)
- Data migrations
- Custom indexes or constraints
- PostgreSQL ENUM type changes

## Run Migrations

```bash
# Apply all pending migrations
mise run migrate

# Check current version
uv run alembic current

# See migration history
uv run alembic history
```

## Migration Structure

```python
"""Add widgets table.

Revision ID: 009
Revises: 008
Create Date: 2026-03-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "widgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=19, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_widgets_group_id", "widgets", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_widgets_group_id", table_name="widgets")
    op.drop_table("widgets")
```

## Rules

- Always use `DateTime(timezone=True)` — never naive timestamps
- Use `server_default=sa.text("now()")` for timestamp columns
- Use `server_default="true"` / `server_default="false"` for booleans
- Create ENUM types with idempotent `DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN null; END $$`
- Drop indexes before dropping tables in `downgrade()`
- Drop ENUM types only in `downgrade()` after the table is gone

## PostgreSQL ENUMs

When adding a new ENUM column, create the type explicitly in the migration:

```python
def upgrade() -> None:
    op.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE widgetstatus AS ENUM ('ACTIVE', 'ARCHIVED', 'DELETED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    op.create_table(
        "widgets",
        sa.Column("status", sa.Enum("ACTIVE", "ARCHIVED", "DELETED",
                  name="widgetstatus"), nullable=False, server_default="ACTIVE"),
        # ...
    )

def downgrade() -> None:
    op.drop_table("widgets")
    op.execute("DROP TYPE IF EXISTS widgetstatus")
```

## Rollback

```bash
# Rollback last migration
uv run alembic downgrade -1

# Rollback to a specific revision
uv run alembic downgrade 007
```

## Test Database

Tests auto-create tables from SQLModel metadata, not from migrations. If you change the ORM model,
tests pick up the change automatically. The migrations are used for the development and production
databases.

To verify migrations work correctly, run integration tests:

```bash
mise run test:integration
```
