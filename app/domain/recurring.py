"""Pure domain functions for recurring cost calculations.

Allowed imports: stdlib + external validation libs (sqlmodel, pydantic) per ADR-011
Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
"""

from decimal import ROUND_HALF_UP, Decimal

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
