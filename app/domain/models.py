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

from sqlmodel import Field, SQLModel  # noqa: F401


class RecurringFrequency(StrEnum):
    """Supported recurring cost frequencies."""

    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    SEMI_ANNUALLY = "SEMI_ANNUALLY"
    YEARLY = "YEARLY"
    EVERY_N_MONTHS = "EVERY_N_MONTHS"


class SplitType(StrEnum):
    """Supported expense split types."""

    EVEN = "EVEN"
    SHARES = "SHARES"  # Weighted split: each person gets N shares
    PERCENTAGE = "PERCENTAGE"  # Percentage split: must sum to 100%
    EXACT = "EXACT"  # Exact amounts: must sum to expense total


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

    PENDING = "PENDING"  # Default, included in balance and settlement
    GIFT = "GIFT"  # Excluded from balance and settlement
    SETTLED = "SETTLED"  # Immutable after settlement confirmation


class ExpenseBase(SQLModel):
    """Domain base for Expense — validation + business data. No table."""

    amount: Decimal = Field(decimal_places=2, ge=0.01)
    description: str = Field(max_length=255)
    date: date
    creator_id: int
    payer_id: int
    currency: str = Field(max_length=3)
    split_type: SplitType = Field(default=SplitType.EVEN)
    status: ExpenseStatus = Field(default=ExpenseStatus.PENDING)
    recurring_definition_id: int | None = Field(default=None)
    billing_period: str | None = Field(default=None, max_length=10)
    is_auto_generated: bool = Field(default=False)


class ExpensePublic(ExpenseBase):
    """Output schema for Expense — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime


class ExpenseSplitBase(SQLModel):
    """Domain base for ExpenseSplit — validation + business data. No table."""

    expense_id: int
    user_id: int
    amount: Decimal = Field(decimal_places=2, ge=0)
    share_value: Decimal | None = Field(default=None, decimal_places=4)


class ExpenseSplitPublic(ExpenseSplitBase):
    """Output schema for ExpenseSplit — includes DB-generated fields."""

    id: int
    created_at: datetime


class ExpenseNoteBase(SQLModel):
    """Domain base for ExpenseNote — validation + business data. No table."""

    expense_id: int
    author_id: int
    content: str = Field(min_length=1, max_length=2000)


class ExpenseNotePublic(ExpenseNoteBase):
    """Output schema for ExpenseNote — includes DB-generated fields."""

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

    reference_id: str = Field(max_length=100)
    settled_by_id: int
    settled_at: datetime


class SettlementPublic(SettlementBase):
    """Output schema for Settlement — includes DB-generated fields."""

    id: int
    created_at: datetime


class RecurringDefinitionBase(SQLModel):
    """Domain base for RecurringDefinition — validation + business data. No table."""

    name: str = Field(max_length=255)
    amount: Decimal = Field(decimal_places=2, ge=0.01)
    frequency: RecurringFrequency
    interval_months: int | None = Field(default=None)
    next_due_date: date
    payer_id: int
    split_type: SplitType = Field(default=SplitType.EVEN)
    split_config: dict | None = Field(default=None)
    category: str | None = Field(default=None, max_length=50)
    auto_generate: bool = Field(default=False)
    is_active: bool = Field(default=True)
    currency: str = Field(max_length=3)


class RecurringDefinitionPublic(RecurringDefinitionBase):
    """Output schema for RecurringDefinition — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


# ---------------------------------------------------------------------------
# Epic 3: Trips
# ---------------------------------------------------------------------------


class TripBase(SQLModel):
    """Domain base for Trip — validation + business data. No table."""

    name: str = Field(max_length=255)
    currency: str = Field(max_length=3)
    sharing_token: str = Field(max_length=64, index=True, unique=True)
    is_active: bool = Field(default=True)
    created_by_id: int


class TripPublic(TripBase):
    """Output schema for Trip — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime


class GuestBase(SQLModel):
    """Domain base for Guest (Global Address Book). No table."""

    name: str = Field(max_length=255)
    user_id: int | None = Field(default=None)


class GuestPublic(GuestBase):
    """Output schema for Guest."""

    id: int


class TripParticipantBase(SQLModel):
    """Domain base for TripParticipant mapping."""

    trip_id: int
    guest_id: int


class TripExpenseBase(SQLModel):
    """Domain base for TripExpense. No table."""

    trip_id: int
    description: str = Field(max_length=255)
    amount: Decimal = Field(decimal_places=2, ge=0.01)
    date: date
    paid_by_id: int
    created_by_guest_id: int


class TripExpensePublic(TripExpenseBase):
    """Output schema for TripExpense."""

    id: int
    created_at: datetime
    updated_at: datetime


class TripExpenseSplitBase(SQLModel):
    """Domain base for TripExpenseSplit. No table."""

    trip_expense_id: int
    guest_id: int
    amount: Decimal = Field(decimal_places=2, ge=0)
    share_value: Decimal | None = Field(default=None, decimal_places=4)


class TripExpenseSplitPublic(TripExpenseSplitBase):
    """Output schema for TripExpenseSplit."""

    id: int
    created_at: datetime


class TripExpenseNoteBase(SQLModel):
    """Domain base for TripExpenseNote. No table."""

    trip_expense_id: int
    author_id: int
    content: str = Field(min_length=1, max_length=2000)


class TripExpenseNotePublic(TripExpenseNoteBase):
    """Output schema for TripExpenseNote."""

    id: int
    created_at: datetime
    updated_at: datetime
