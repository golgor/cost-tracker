from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.adapters.sqlalchemy.queries.dashboard_queries import (
    calculate_balance,
    get_group_expenses,
    get_group_members,
    get_this_month_total,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.web.templates import setup_templates

router = APIRouter(tags=["dashboard"])
templates = setup_templates("app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Dashboard page showing balance bar, expense feed, and widgets.

    Performance: Must load in under 1 second (NFR1).
    """
    with uow:
        user_domain = uow.users.get_by_id(user_id)
        if user_domain is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get user's primary group (MVP1: single household per user)
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            # Redirect to setup wizard if no group exists
            return templates.TemplateResponse(
                request,
                "dashboard/empty_state_setup.html",
                {
                    "user": user_domain,
                    "csrf_token": getattr(request.state, "csrf_token", ""),
                },
            )

        # Fetch dashboard data via read-only queries
        expenses = get_group_expenses(uow.session, group.id)
        balance_data = calculate_balance(uow.session, group.id, user_id)
        this_month_total = get_this_month_total(uow.session, group.id)

        # Get all group members for badge colors/names in expense feed
        members = get_group_members(uow.session, group.id)

        # Fetch user data for displaying names (bulk fetch to avoid N+1)
        member_user_ids = [m.user_id for m in members]
        users_by_id = {}
        for user_id in member_user_ids:
            user = uow.users.get_by_id(user_id)
            if user:
                users_by_id[user_id] = user
            else:
                # Log data integrity issue: group member references non-existent user
                import structlog

                logger = structlog.get_logger()
                logger.warning(
                    "group_member_references_missing_user",
                    group_id=group.id,
                    user_id=user_id,
                )

    # Currency symbol mapping for form display
    currency_symbols = {
        "EUR": "€",
        "USD": "$",
        "GBP": "£",
        "SEK": "kr",
    }

    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "user": user_domain,
            "group": group,
            "expenses": expenses,
            "balance": balance_data,
            "this_month_total": this_month_total,
            "group_members": members,  # List of MembershipPublic for forms
            "users": users_by_id,
            "current_user_id": user_id,  # For form defaults
            "today": date.today().isoformat(),  # For date field default
            "currency_symbol": currency_symbols.get(group.default_currency, group.default_currency),
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
