"""Pydantic response models for the external API (Glance Dashboard integration).

Money values are serialized as string Decimals (e.g. "123.45"), never floats.
Dates are ISO 8601 strings.
"""

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
