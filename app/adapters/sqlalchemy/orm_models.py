from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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
    joined_at: datetime = Field(default_factory=_utc_now)


class UserRow(UserBase, table=True):
    """ORM model for User — inherits from domain base, adds DB fields."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class GroupRow(GroupBase, table=True):
    """ORM model for Group — inherits from domain base, adds DB fields."""

    __tablename__ = "groups"

    id: int | None = Field(default=None, primary_key=True)
    singleton_guard: bool = Field(default=True, unique=True, nullable=False)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


# Re-export SQLModel for Alembic env.py
__all__ = ["SQLModel", "UserRow", "GroupRow", "MembershipRow"]
