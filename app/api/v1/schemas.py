"""Pydantic response models for the external API (Glance Dashboard integration).

Money values are serialized as string Decimals (e.g. "123.45"), never floats.
Dates are ISO 8601 strings.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class MemberBalance(BaseModel):
    name: str
    net: str


class BalanceSummary(BaseModel):
    net_amount: str
    direction: str
    members: list[MemberBalance]


class MonthSummary(BaseModel):
    period: str
    total: str
    currency: str
    expense_count: int
    unsettled_count: int
    balance: BalanceSummary


class UpcomingRecurring(BaseModel):
    name: str
    amount: str
    next_due_date: str
    frequency: str
    payer: str


class RecurringSummary(BaseModel):
    active_count: int
    total_monthly_cost: str
    currency: str
    upcoming: list[UpcomingRecurring]


class GlanceSummary(BaseModel):
    month: MonthSummary
    recurring: RecurringSummary


class ExpenseCreateRequest(BaseModel):
    amount: Decimal
    description: str
    date: date | None = None
    creator_id: int
    payer_id: int
    member_ids: list[int]
    currency: str = "EUR"
    split_type: str = "EVEN"
    split_config: dict[int, Decimal] | None = None


class ExpenseUpdateRequest(BaseModel):
    amount: Decimal | None = None
    description: str | None = None
    date: date | None = None
    payer_id: int | None = None
    currency: str | None = None
    split_type: str | None = None
    split_config: dict[int, Decimal] | None = None
    member_ids: list[int] | None = None
