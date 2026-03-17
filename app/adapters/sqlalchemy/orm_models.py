from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.domain.models import GroupBase, MemberRole, UserBase

# SQLModel.metadata serves as the declarative base for Alembic migrations.
# Table models (XxxRow) inherit from domain models with table=True.
# Domain models are defined in app/domain/models.py without table=True.

UTC = ZoneInfo("UTC")


def _utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class MembershipRow(SQLModel, table=True):
    """User-Group membership join table with role."""

    __tablename__ = "group_memberships"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    group_id: int = Field(foreign_key="groups.id", primary_key=True)
    role: MemberRole = Field(default=MemberRole.USER)
    joined_at: datetime = Field(default_factory=_utc_now, sa_type=DateTime(timezone=True))  # type: ignore[arg-type]


class UserRow(UserBase, table=True):
    """ORM model for User — inherits from domain base, adds DB fields."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utc_now, sa_type=DateTime(timezone=True))  # type: ignore[arg-type]
    updated_at: datetime = Field(default_factory=_utc_now, sa_type=DateTime(timezone=True))  # type: ignore[arg-type]


class GroupRow(GroupBase, table=True):
    """ORM model for Group — inherits from domain base, adds DB fields."""

    __tablename__ = "groups"

    id: int | None = Field(default=None, primary_key=True)
    singleton_guard: bool = Field(default=True, unique=True, nullable=False)
    created_at: datetime = Field(default_factory=_utc_now, sa_type=DateTime(timezone=True))  # type: ignore[arg-type]
    updated_at: datetime = Field(default_factory=_utc_now, sa_type=DateTime(timezone=True))  # type: ignore[arg-type]


class AuditRow(SQLModel, table=True):
    """ORM model for audit log entries."""

    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    actor_id: int = Field(index=True)
    action: str = Field(max_length=100, index=True)
    entity_type: str = Field(max_length=100, index=True)
    entity_id: int = Field(index=True)
    occurred_at: datetime = Field(
        default_factory=_utc_now,
        sa_type=DateTime(timezone=True),  # type: ignore[arg-type]
        index=True,
    )
    details: dict[str, Any] | None = Field(
        default=None,
        sa_column=sa.Column(sa.JSON, nullable=True),
    )


# Re-export SQLModel for Alembic env.py
__all__ = ["SQLModel", "UserRow", "GroupRow", "MembershipRow", "AuditRow"]
