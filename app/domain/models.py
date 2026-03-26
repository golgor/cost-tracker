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

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlmodel import Field, SQLModel  # noqa: F401


class SplitType(StrEnum):
    """Supported expense split types."""

    EVEN = "EVEN"
    # Future: SHARES, PERCENTAGE, EXACT


class MemberRole(StrEnum):
    """User roles within a household group."""

    ADMIN = "ADMIN"
    USER = "USER"


class UserRole(StrEnum):
    """App-level user roles for admin/lifecycle management."""

    ADMIN = "ADMIN"
    USER = "USER"


class UserBase(SQLModel):
    """Domain base for User — validation + business data. No table."""

    oidc_sub: str = Field(index=True, unique=True)
    email: str = Field(max_length=255)
    display_name: str = Field(max_length=255)
    role: UserRole = Field(default=UserRole.USER)
    is_active: bool = Field(default=True)
    deactivated_at: datetime | None = Field(default=None)
    deactivated_by_user_id: int | None = Field(default=None)


class UserPublic(UserBase):
    """Output schema for User — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime

    @property
    def is_admin(self) -> bool:
        """Pre-computed boolean flag for template visibility checks."""
        return self.role == UserRole.ADMIN


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


class ExpenseStatus(StrEnum):
    """Expense lifecycle status."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    GIFT = "GIFT"
    SETTLED = "SETTLED"  # Added for Epic 2.4 - expenses locked after settlement


class ExpenseBase(SQLModel):
    """Domain base for Expense — validation + business data. No table."""

    group_id: int
    amount: Decimal = Field(decimal_places=2, ge=0.01)
    description: str = Field(max_length=255)
    date: date
    creator_id: int
    payer_id: int
    currency: str = Field(max_length=3)
    split_type: SplitType = Field(default=SplitType.EVEN)
    status: ExpenseStatus = Field(default=ExpenseStatus.PENDING)


class ExpensePublic(ExpenseBase):
    """Output schema for Expense — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime


class SettlementTransactionBase(SQLModel):
    """Domain base for individual settlement transactions."""

    settlement_id: int
    from_user_id: int
    to_user_id: int
    amount: Decimal = Field(decimal_places=2, ge=0)


class SettlementTransactionPublic(SettlementTransactionBase):
    """Output schema for SettlementTransaction — includes DB-generated fields."""

    id: int


class SettlementBase(SQLModel):
    """Domain base for Settlement — validation + business data. No table."""

    group_id: int
    reference_id: str = Field(max_length=100)
    settled_by_id: int
    settled_at: datetime


class SettlementPublic(SettlementBase):
    """Output schema for Settlement — includes DB-generated fields."""

    id: int
    created_at: datetime
