from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, func
from sqlmodel import Field, SQLModel

from app.domain.models import GroupBase, MemberRole, UserBase, UserRole

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
    role: UserRole = Field(  # type: ignore[assignment]
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


# Re-export SQLModel for Alembic env.py
__all__ = ["SQLModel", "UserRow", "GroupRow", "MembershipRow", "AuditRow"]
