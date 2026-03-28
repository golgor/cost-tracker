"""Pure domain functions for recurring cost calculations.

Allowed imports: stdlib + external validation libs (sqlmodel, pydantic) per ADR-011
Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from dateutil.relativedelta import relativedelta

from app.domain.models import RecurringFrequency

_TWO_PLACES = Decimal("0.01")


def normalized_monthly_cost(
    amount: Decimal,
    frequency: RecurringFrequency,
    interval_months: int | None = None,
) -> Decimal:
    """Calculate the normalized monthly cost for a recurring definition.

    Args:
        amount: The recurring amount in its native frequency.
        frequency: The billing frequency.
        interval_months: Required when frequency is EVERY_N_MONTHS; ignored otherwise.

    Returns:
        The monthly equivalent as a Decimal rounded to 2 decimal places (ROUND_HALF_UP).
    """
    match frequency:
        case RecurringFrequency.MONTHLY:
            result = amount
        case RecurringFrequency.QUARTERLY:
            result = amount / 3
        case RecurringFrequency.SEMI_ANNUALLY:
            result = amount / 6
        case RecurringFrequency.YEARLY:
            result = amount / 12
        case RecurringFrequency.EVERY_N_MONTHS:
            if interval_months is None or interval_months < 1:
                raise ValueError("interval_months must be >= 1 for EVERY_N_MONTHS frequency")
            result = amount / interval_months

    return result.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def advance_due_date(
    current_date: date,
    frequency: RecurringFrequency,
    interval_months: int | None = None,
) -> date:
    """Calculate the next due date given the current one and frequency.

    Uses relativedelta for correct month-boundary arithmetic (e.g. Jan 31 + 1 month = Feb 28).

    Args:
        current_date: The current due date to advance from.
        frequency: The billing frequency.
        interval_months: Required when frequency is EVERY_N_MONTHS; ignored otherwise.

    Returns:
        The next due date after advancing by one billing cycle.
    """
    match frequency:
        case RecurringFrequency.MONTHLY:
            return current_date + relativedelta(months=1)
        case RecurringFrequency.QUARTERLY:
            return current_date + relativedelta(months=3)
        case RecurringFrequency.SEMI_ANNUALLY:
            return current_date + relativedelta(months=6)
        case RecurringFrequency.YEARLY:
            return current_date + relativedelta(years=1)
        case RecurringFrequency.EVERY_N_MONTHS:
            if interval_months is None or interval_months < 1:
                raise ValueError("interval_months must be >= 1 for EVERY_N_MONTHS frequency")
            return current_date + relativedelta(months=interval_months)


def billing_period_for(due_date: date) -> str:
    """Return the billing period string (YYYY-MM) for a given due date."""
    return due_date.strftime("%Y-%m")


def format_expense_description(name: str, billing_period: str) -> str:
    """Format the auto-generated expense description.

    Args:
        name: The recurring definition name (e.g. "Netflix")
        billing_period: ISO year-month string (e.g. "2026-05")

    Returns:
        Description like "Netflix – May 2026"
    """
    year, month = billing_period.split("-")
    label_date = date(int(year), int(month), 1)
    return f"{name} \u2013 {label_date.strftime('%b %Y')}"
