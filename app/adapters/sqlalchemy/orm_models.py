from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, func
from sqlmodel import Field, SQLModel

from app.domain.models import (
    ExpenseBase,
    ExpenseSplitBase,
    ExpenseStatus,
    GroupBase,
    MemberRole,
    SettlementBase,
    SettlementTransactionBase,
    SplitType,
    UserBase,
    UserRole,
)

# SQLModel.metadata serves as the declarative base for Alembic migrations.
# Table models (XxxRow) inherit from domain models with table=True.
# Domain models are defined in app/domain/models.py without table=True.

# Timestamp column helpers — DB generates values via server_default / onupdate.
_TZ_DATETIME = DateTime(timezone=True)


class MembershipRow(SQLModel, table=True):
    """User-Group membership join table with role."""

    __tablename__ = "group_memberships"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    group_id: int = Field(foreign_key="groups.id", primary_key=True)
    role: MemberRole = Field(
        default=MemberRole.USER,
        sa_type=sa.Enum(MemberRole, name="roletype", native_enum=True),  # type: ignore[arg-type]
    )
    joined_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )


class UserRow(UserBase, table=True):
    """ORM model for User — inherits from domain base, adds DB fields."""

    __tablename__ = "users"

    # Override role field to use PostgreSQL ENUM
    role: UserRole = Field(
        default=UserRole.USER,
        sa_type=sa.Enum(UserRole, name="roletype", native_enum=True),  # type: ignore[arg-type]
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


class GroupRow(GroupBase, table=True):
    """ORM model for Group — inherits from domain base, adds DB fields."""

    __tablename__ = "groups"

    # Override default_split_type to use PostgreSQL ENUM
    default_split_type: SplitType = Field(
        default=SplitType.EVEN,
        sa_type=sa.Enum(SplitType, name="splittype", native_enum=True),  # type: ignore[arg-type]
    )

    id: int | None = Field(default=None, primary_key=True)
    singleton_guard: bool = Field(default=True, unique=True, nullable=False)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )
    updated_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
    )


class AuditRow(SQLModel, table=True):
    """ORM model for audit log entries."""

    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    actor_id: int = Field(index=True)
    action: str = Field(max_length=100, index=True)
    entity_type: str = Field(max_length=100, index=True)
    entity_id: int = Field(index=True)
    occurred_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,  # type: ignore[arg-type]
        index=True,
    )
    changes: dict[str, Any] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )


class ExpenseRow(ExpenseBase, table=True):
    """ORM model for Expense — inherits from domain base, adds DB fields."""

    __tablename__ = "expenses"

    # Override status to use PostgreSQL ENUM
    status: ExpenseStatus = Field(
        default=ExpenseStatus.PENDING,
        sa_type=sa.Enum(ExpenseStatus, name="expensestatus", native_enum=True),  # type: ignore[arg-type]
    )

    # Override split_type to use PostgreSQL ENUM
    split_type: SplitType = Field(
        default=SplitType.EVEN,
        sa_type=sa.Enum(SplitType, name="splittype", native_enum=True),  # type: ignore[arg-type]
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
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
        sa.Index("ix_expenses_group_id_date", "group_id", "date"),
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


class SettlementRow(SettlementBase, table=True):
    """ORM model for Settlement — inherits from domain base, adds DB fields."""

    __tablename__ = "settlements"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["settled_by_id"], ["users.id"]),
        sa.Index("ix_settlements_group_id_settled_at", "group_id", "settled_at"),
        sa.UniqueConstraint("group_id", "reference_id", name="uq_group_reference"),
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

    settlement_id: int = Field(foreign_key="settlements.id", primary_key=True)
    expense_id: int = Field(foreign_key="expenses.id", primary_key=True)


# Re-export SQLModel for Alembic env.py
__all__ = [
    "SQLModel",
    "UserRow",
    "GroupRow",
    "MembershipRow",
    "AuditRow",
    "ExpenseRow",
    "ExpenseSplitRow",
    "SettlementRow",
    "SettlementTransactionRow",
    "SettlementExpenseRow",
]
