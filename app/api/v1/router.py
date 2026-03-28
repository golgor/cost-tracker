"""External API routes for Glance Dashboard integration.

Read-only endpoints returning JSON summaries of household expenses.
Protected by Bearer token authentication (GLANCE_API_KEY).
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.adapters.sqlalchemy.queries.api_queries import (
    get_balance_summary,
    get_default_group_id,
    get_group_currency,
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

router = APIRouter(prefix="/api/v1", tags=["api"], dependencies=[Depends(verify_api_key)])

DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("/summary", response_model=GlanceSummary)
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
    upcoming = [
        UpcomingRecurring(
            name=d["name"],
            amount=str(d["amount"]),
            next_due_date=str(d["next_due_date"]),
            frequency=d["frequency_label"],
            payer=d["payer_display_name"],
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
                    MemberBalance(name=m["name"], net=m["net"])
                    for m in balance_data["members"]
                ],
            ),
        ),
        recurring=RecurringSummary(
            active_count=registry["active_count"],
            total_monthly_cost=registry["total_monthly_cost"],
            currency=registry["currency"],
            upcoming=upcoming,
        ),
    )


def _empty_summary() -> GlanceSummary:
    """Return an empty summary when no group exists."""
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
            total_monthly_cost="0",
            currency="EUR",
            upcoming=[],
        ),
    )
