"""External API routes for Glance Dashboard integration.

Read-only endpoints returning JSON summaries of household expenses.
Protected by Bearer token authentication (GLANCE_API_KEY).

Mounted as a sub-application at /api/v1 so it gets its own OpenAPI docs
at /api/v1/docs without exposing the web (HTMX) routes.
"""

from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from sqlmodel import Session

from app.adapters.sqlalchemy.queries.api_queries import (
    get_balance_summary,
    get_default_group_id,
    get_group_currency,
    get_member_display_names,
    get_this_month_expense_count,
)
from app.adapters.sqlalchemy.queries.dashboard_queries import get_this_month_total
from app.adapters.sqlalchemy.queries.recurring_queries import (
    get_active_definitions,
    get_registry_summary,
)
from app.adapters.sqlalchemy.queries.settlement_queries import get_unsettled_count
from app.api.v1.auth import verify_api_key
from app.api.v1.schemas import (
    BalanceSummary,
    GlanceSummary,
    MemberBalance,
    MonthSummary,
    RecurringSummary,
    UpcomingRecurring,
)
from app.dependencies import get_db_session
from app.domain.models import RecurringFrequency

api_v1 = FastAPI(
    title="Cost Tracker API",
    version="1.0.0",
    description="Read-only API for Glance Dashboard integration.",
    dependencies=[Depends(verify_api_key)],
)

DbSession = Annotated[Session, Depends(get_db_session)]

_FREQUENCY_LABELS: dict[RecurringFrequency, str] = {
    RecurringFrequency.MONTHLY: "monthly",
    RecurringFrequency.QUARTERLY: "quarterly",
    RecurringFrequency.SEMI_ANNUALLY: "semi-annually",
    RecurringFrequency.YEARLY: "yearly",
    RecurringFrequency.EVERY_N_MONTHS: "every N months",
}


def _format_money(value: str) -> str:
    """Ensure money strings have two decimal places (e.g. '0' → '0.00')."""
    from decimal import Decimal

    return str(Decimal(value).quantize(Decimal("0.01")))


def _frequency_label(frequency: RecurringFrequency, interval_months: int | None) -> str:
    """Human-readable frequency label."""
    if frequency == RecurringFrequency.EVERY_N_MONTHS and interval_months:
        return f"every {interval_months} months"
    return _FREQUENCY_LABELS.get(frequency, frequency.value.lower())


@api_v1.get("/summary", response_model=GlanceSummary)
def get_summary(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> GlanceSummary:
    """Return a combined summary for Glance Dashboard widgets.

    Includes current month totals, balance between partners,
    recurring cost overview, and upcoming scheduled expenses.
    """
    group_id = get_default_group_id(session)
    if group_id is None:
        return _empty_summary()

    currency = get_group_currency(session, group_id)

    # Month data
    month_total = get_this_month_total(session, group_id)
    expense_count = get_this_month_expense_count(session, group_id)
    unsettled_count = get_unsettled_count(session, group_id)
    balance_data = get_balance_summary(session, group_id)

    today = date.today()
    period = f"{today.year}-{today.month:02d}"

    # Recurring data
    registry = get_registry_summary(session, group_id)
    active_defs = get_active_definitions(session, group_id)
    display_names = get_member_display_names(session, group_id)
    upcoming = [
        UpcomingRecurring(
            name=d.name,
            amount=str(d.amount),
            next_due_date=str(d.next_due_date),
            frequency=_frequency_label(d.frequency, d.interval_months),
            payer=display_names.get(d.payer_id, "Unknown"),
        )
        for d in active_defs[:limit]
    ]

    return GlanceSummary(
        month=MonthSummary(
            period=period,
            total=str(month_total),
            currency=currency,
            expense_count=expense_count,
            unsettled_count=unsettled_count,
            balance=BalanceSummary(
                net_amount=balance_data["net_amount"],
                direction=balance_data["direction"],
                members=[
                    MemberBalance(name=m["name"], net=m["net"]) for m in balance_data["members"]
                ],
            ),
        ),
        recurring=RecurringSummary(
            active_count=registry["active_count"],
            total_monthly_cost=_format_money(registry["total_monthly_cost"]),
            currency=registry["currency"],
            upcoming=upcoming,
        ),
    )


def _empty_summary() -> GlanceSummary:
    """Return an empty summary when no group exists.

    Uses EUR as fallback currency since there is no group to source it from.
    """
    return GlanceSummary(
        month=MonthSummary(
            period=f"{date.today().year}-{date.today().month:02d}",
            total="0.00",
            currency="EUR",
            expense_count=0,
            unsettled_count=0,
            balance=BalanceSummary(
                net_amount="0.00",
                direction="All square",
                members=[],
            ),
        ),
        recurring=RecurringSummary(
            active_count=0,
            total_monthly_cost="0.00",
            currency="EUR",
            upcoming=[],
        ),
    )
