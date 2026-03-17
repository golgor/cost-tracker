# Domain models using SQLModel (without table=True for pure data + validation)
#
# Allowed imports: sqlmodel, pydantic, typing, decimal, datetime, enum (external libs)
# Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
#
# Pattern (Story 1.4+):
#   class ExpenseBase(SQLModel):
#       """Domain model — validation + business data. No table."""
#       amount: Decimal = Field(ge=0)
#       description: str = Field(max_length=255)
#       ...
#
#   class ExpenseCreate(ExpenseBase):
#       """Input schema for creating expense."""
#       pass
#
#   class ExpensePublic(ExpenseBase):
#       """Output schema — includes DB-generated fields."""
#       id: int
#       created_at: datetime

from datetime import datetime
from enum import Enum
from typing import Any

from sqlmodel import Field, SQLModel  # noqa: F401


class SplitType(str, Enum):
    """Supported expense split types."""

    EVEN = "even"
    # Future: SHARES, PERCENTAGE, EXACT


class MemberRole(str, Enum):
    """User roles within a household group."""

    ADMIN = "admin"
    USER = "user"


class UserBase(SQLModel):
    """Domain base for User — validation + business data. No table."""

    oidc_sub: str = Field(index=True, unique=True)
    email: str = Field(max_length=255)
    display_name: str = Field(max_length=255)


class UserPublic(UserBase):
    """Output schema for User — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime


class GroupBase(SQLModel):
    """Domain base for Group — validation + business data. No table."""

    name: str = Field(max_length=100)
    default_currency: str = Field(default="EUR", max_length=3)
    default_split_type: SplitType = Field(default=SplitType.EVEN)
    tracking_threshold: int = Field(default=30, ge=1, le=365)


class GroupPublic(GroupBase):
    """Output schema for Group — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime


class MembershipPublic(SQLModel):
    """Output schema for group membership."""

    user_id: int
    group_id: int
    role: MemberRole
    joined_at: datetime


class AuditEntry(SQLModel):
    """Output schema for an audit log entry."""

    id: int
    actor_id: int
    action: str
    entity_type: str
    entity_id: int
    occurred_at: datetime
    changes: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Expense conceptual model — design skeleton for Epic 2 (FR42)
#
# Key distinction: creator_id vs payer_id
#   - creator_id: the user who entered the expense into the system
#   - payer_id:   the user who actually paid the real-world bill
#
# These are often the same person but must remain separate fields so the
# system can model the case where Partner A records an expense but Partner B
# was the one who paid (e.g. Partner A enters a utility bill that Partner B
# already paid). Settlement math always uses payer_id.
#
# Full implementation is deferred to Epic 2. This comment documents the
# decision so Epic 2 can build without ambiguity.
# ---------------------------------------------------------------------------
