"""Pydantic response models for the external API (Glance Dashboard integration).

Money values are serialized as string Decimals (e.g. "123.45"), never floats.
Dates are ISO 8601 strings.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.models import SplitType


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
    amount: Decimal = Field(gt=0, decimal_places=2)
    description: str = Field(min_length=1, max_length=255)
    date: date | None = None
    creator_id: int
    payer_id: int
    member_ids: list[int]
    currency: str = Field(default="EUR", max_length=3)
    split_type: SplitType = SplitType.EVEN
    split_config: dict[int, Decimal] | None = None


class ExpenseUpdateRequest(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    description: str | None = Field(default=None, max_length=255)
    date: date | None = None
    payer_id: int | None = None
    currency: str | None = Field(default=None, max_length=3)
    split_type: SplitType | None = None
    split_config: dict[int, Decimal] | None = None
    member_ids: list[int] | None = None
