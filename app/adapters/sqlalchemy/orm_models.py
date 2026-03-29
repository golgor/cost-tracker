from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import DateTime, func
from sqlmodel import Field, SQLModel

from app.domain.models import (
    ExpenseBase,
    ExpenseNoteBase,
    ExpenseSplitBase,
    ExpenseStatus,
    RecurringDefinitionBase,
    RecurringFrequency,
    SettlementBase,
    SettlementTransactionBase,
    SplitType,
    UserBase,
)

# SQLModel.metadata serves as the declarative base for Alembic migrations.
# Table models (XxxRow) inherit from domain models with table=True.
# Domain models are defined in app/domain/models.py without table=True.

# Timestamp column helpers — DB generates values via server_default / onupdate.
_TZ_DATETIME = DateTime(timezone=True)


class UserRow(UserBase, table=True):
    """ORM model for User — inherits from domain base, adds DB fields."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )
    updated_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )


class ExpenseRow(ExpenseBase, table=True):
    """ORM model for Expense — inherits from domain base, adds DB fields."""

    __tablename__ = "expenses"

    # Override status to use VARCHAR + CHECK constraint
    status: ExpenseStatus = Field(
        default=ExpenseStatus.PENDING,
        sa_type=sa.String(length=20),  # type: ignore[arg-type]
    )

    # Override split_type to use VARCHAR + CHECK constraint
    split_type: SplitType = Field(
        default=SplitType.EVEN,
        sa_type=sa.String(length=20),  # type: ignore[arg-type]
    )

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )
    updated_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )
    amount: Decimal = Field(
        sa_type=sa.Numeric(precision=19, scale=2),  # type: ignore[arg-type]
    )

    # Foreign key constraints
    __table_args__ = (
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["recurring_definition_id"],
            ["recurring_definitions.id"],
            ondelete="SET NULL",
            name="fk_expenses_recurring_definition_id",
        ),
        sa.Index("ix_expenses_date", "date"),
    )


class ExpenseSplitRow(ExpenseSplitBase, table=True):
    """ORM model for ExpenseSplit — stores calculated split amounts per user."""

    __tablename__ = "expense_splits"

    id: int | None = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expenses.id", index=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    amount: Decimal = Field(
        sa_type=sa.Numeric(precision=19, scale=2),  # type: ignore[arg-type]
    )
    share_value: Decimal | None = Field(
        default=None,
        sa_type=sa.Numeric(precision=19, scale=4),  # type: ignore[arg-type]
    )
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )

    __table_args__ = (
        sa.UniqueConstraint("expense_id", "user_id", name="uq_expense_user"),
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )


class ExpenseNoteRow(ExpenseNoteBase, table=True):
    """ORM model for ExpenseNote — stores notes/comments on expenses."""

    __tablename__ = "expense_notes"

    id: int | None = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="expenses.id", index=True)
    author_id: int = Field(foreign_key="users.id", index=True)
    content: str = Field(sa_type=sa.Text)  # type: ignore[arg-type]
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )
    updated_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["expense_id"],
            ["expenses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.Index("ix_expense_notes_expense_id_created_at", "expense_id", "created_at"),
    )


class SettlementRow(SettlementBase, table=True):
    """ORM model for Settlement — inherits from domain base, adds DB fields."""

    __tablename__ = "settlements"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(["settled_by_id"], ["users.id"]),
        sa.Index("ix_settlements_settled_at", "settled_at"),
        sa.UniqueConstraint("reference_id", name="uq_reference"),
    )


class SettlementTransactionRow(SettlementTransactionBase, table=True):
    """ORM model for individual settlement transactions."""

    __tablename__ = "settlement_transactions"

    id: int | None = Field(default=None, primary_key=True)
    settlement_id: int = Field(foreign_key="settlements.id", index=True)
    amount: Decimal = Field(sa_type=sa.Numeric(precision=19, scale=2))
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["settlement_id"],
            ["settlements.id"],
            ondelete="CASCADE",
        ),
    )


class SettlementExpenseRow(SQLModel, table=True):
    """Join table linking settlements to expenses."""

    __tablename__ = "settlement_expenses"

    settlement_id: int = Field(primary_key=True)
    expense_id: int = Field(primary_key=True)

    __table_args__ = (
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
    )


class RecurringDefinitionRow(RecurringDefinitionBase, table=True):
    """ORM model for RecurringDefinition — inherits from domain base, adds DB fields."""

    __tablename__ = "recurring_definitions"

    # Override frequency to use VARCHAR + CHECK constraint
    frequency: RecurringFrequency = Field(
        sa_type=sa.String(length=20),  # type: ignore[arg-type]
    )

    # Override split_type to use VARCHAR + CHECK constraint
    split_type: SplitType = Field(
        default=SplitType.EVEN,
        sa_type=sa.String(length=20),  # type: ignore[arg-type]
    )

    # Override amount to use exact numeric type
    amount: Decimal = Field(
        sa_type=sa.Numeric(precision=19, scale=2),  # type: ignore[arg-type]
    )

    # Override split_config to use JSON column
    split_config: dict | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )
    updated_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
        sa.Index("ix_recurring_definitions_next_due_date", "next_due_date"),
    )


# Re-export SQLModel for Alembic env.py
__all__ = [
    "SQLModel",
    "UserRow",
    "ExpenseRow",
    "ExpenseSplitRow",
    "SettlementRow",
    "SettlementTransactionRow",
    "SettlementExpenseRow",
    "RecurringDefinitionRow",
]
