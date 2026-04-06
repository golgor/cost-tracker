"""Expense list, filtered feed, and balance endpoints."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.adapters.sqlalchemy.queries.dashboard_queries import (
    calculate_balance,
    get_all_users,
    get_filtered_expenses,
    get_recurring_definition_names,
    get_this_month_total,
)
from app.domain.models import ExpensePublic, UserPublic
from app.settings import settings
from app.web.expenses._shared import (
    CurrentUserId,
    UowDep,
    _build_expense_count_message,
    _has_active_expense_filters,
    _parse_date_filters,
    templates,
)
from app.web.filters import get_currency_symbol
from app.web.view_models import ExpenseCardViewModel

router = APIRouter(tags=["expenses"])


def _to_card_view_models(
    expenses: list[ExpensePublic],
    users_by_id: dict[int, UserPublic],
    currency_symbol: str,
    current_user_id: int,
    recurring_names: dict[int, str],
) -> list[ExpenseCardViewModel]:
    """Transform a list of domain expenses into card view models."""
    result = []
    for expense in expenses:
        payer = users_by_id.get(expense.payer_id)
        payer_name = payer.display_name if payer else "Unknown User"
        rec_def_id = expense.recurring_definition_id
        rec_name = recurring_names.get(rec_def_id) if rec_def_id else None
        result.append(
            ExpenseCardViewModel.from_domain(
                expense=expense,
                payer_name=payer_name,
                currency_symbol=currency_symbol,
                current_user_id=current_user_id,
                recurring_name=rec_name,
            )
        )
    return result


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_list(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    payer_id: int | None = Query(None),
    search_query: str | None = Query(None),
):
    """Dedicated expenses list page with filtering.

    Shows all expenses with filter controls.
    Distinct from dashboard which shows recent expenses only.
    """
    with uow:
        # Get user
        user = uow.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Parse date filters and get filtered expenses
        date_from_parsed, date_to_parsed = _parse_date_filters(date_from, date_to)
        unsettled_expenses = get_filtered_expenses(
            uow.session,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            status="PENDING",
            search_query=search_query or None,
        )
        settled_expenses = get_filtered_expenses(
            uow.session,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            status="SETTLED",
            search_query=search_query or None,
        )

        # Get balance data (filtered when filters are active)
        balance_data = calculate_balance(
            uow.session,
            user_id,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            search_query=search_query.strip() if search_query else None,
        )

        # Get this month total
        this_month_total = get_this_month_total(uow.session)

        # Get all users for display and filters
        users = get_all_users(uow.session)
        users_by_id = {u.id: u for u in users}

        # Collect recurring definition IDs for name lookup
        all_expenses = unsettled_expenses + settled_expenses
        definition_ids = [
            e.recurring_definition_id for e in all_expenses if e.recurring_definition_id is not None
        ]
        recurring_names = get_recurring_definition_names(uow.session, definition_ids)

        # Transform to view models
        currency_symbol = get_currency_symbol(settings.DEFAULT_CURRENCY)
        unsettled_vms = _to_card_view_models(
            unsettled_expenses, users_by_id, currency_symbol, user_id, recurring_names
        )
        settled_vms = _to_card_view_models(
            settled_expenses, users_by_id, currency_symbol, user_id, recurring_names
        )

    # Result count message
    total_expenses = len(unsettled_vms) + len(settled_vms)
    active_search = search_query.strip() if search_query else None
    count_message = _build_expense_count_message(total_expenses, active_search)

    # Check if any filters are active
    has_active_filters = _has_active_expense_filters(date_from, date_to, payer_id)

    return templates.TemplateResponse(
        request,
        "expenses/index.html",
        {
            "user": user,
            "unsettled_expenses": unsettled_vms,
            "settled_expenses": settled_vms,
            "balance": balance_data,
            "this_month_total": this_month_total,
            "users": users_by_id,
            "users_list": users,
            "current_user_id": user_id,
            "today": date.today().isoformat(),
            "currency_symbol": currency_symbol,
            "default_currency": settings.DEFAULT_CURRENCY,
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "count_message": count_message,
            "has_active_filters": has_active_filters,
            "has_active_search": bool(active_search),
            "search_query": active_search or "",
            # Filter values for form persistence
            "filter_date_from": date_from or "",
            "filter_date_to": date_to or "",
            "filter_payer_id": payer_id or "",
        },
    )


@router.get("/expenses/filtered", response_class=HTMLResponse)
async def expenses_filtered(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    payer_id: int | None = Query(None),
    search_query: str | None = Query(None),
):
    """HTMX endpoint for filtered expense feed partial.

    Returns only the expense feed section for HTMX partial swap.
    """
    with uow:
        # Parse date filters and get filtered expenses
        date_from_parsed, date_to_parsed = _parse_date_filters(date_from, date_to)
        active_search = search_query.strip() if search_query else None
        unsettled_expenses = get_filtered_expenses(
            uow.session,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            status="PENDING",
            search_query=active_search,
        )
        settled_expenses = get_filtered_expenses(
            uow.session,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            status="SETTLED",
            search_query=active_search,
        )

        # Get all users for display
        users = get_all_users(uow.session)
        users_by_id = {u.id: u for u in users}

        # Collect recurring definition IDs for name lookup
        all_expenses = unsettled_expenses + settled_expenses
        definition_ids = [
            e.recurring_definition_id for e in all_expenses if e.recurring_definition_id is not None
        ]
        recurring_names = get_recurring_definition_names(uow.session, definition_ids)

    # Transform to view models
    currency_symbol = get_currency_symbol(settings.DEFAULT_CURRENCY)
    unsettled_vms = _to_card_view_models(
        unsettled_expenses, users_by_id, currency_symbol, user_id, recurring_names
    )
    settled_vms = _to_card_view_models(
        settled_expenses, users_by_id, currency_symbol, user_id, recurring_names
    )

    # Result count message
    total_expenses = len(unsettled_vms) + len(settled_vms)
    count_message = _build_expense_count_message(total_expenses, active_search)

    # Check if filters are active
    has_active_filters = _has_active_expense_filters(date_from, date_to, payer_id)

    return templates.TemplateResponse(
        request,
        "expenses/_expense_feed.html",
        {
            "unsettled_expenses": unsettled_vms,
            "settled_expenses": settled_vms,
            "users": users_by_id,
            "current_user_id": user_id,
            "count_message": count_message,
            "has_active_filters": has_active_filters,
            "has_active_search": bool(active_search),
            "search_query": active_search or "",
            "currency_symbol": currency_symbol,
        },
    )


@router.get("/expenses/balance", response_class=HTMLResponse)
async def expenses_balance(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    payer_id: int | None = Query(None),
    search_query: str | None = Query(None),
):
    """HTMX endpoint for filtered balance bar partial."""
    with uow:
        user = uow.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        date_from_parsed, date_to_parsed = _parse_date_filters(date_from, date_to)

        balance_data = calculate_balance(
            uow.session,
            user_id,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            search_query=search_query.strip() if search_query else None,
        )

        users = get_all_users(uow.session)
        users_by_id = {u.id: u for u in users}

    return templates.TemplateResponse(
        request,
        "expenses/_balance_bar.html",
        {
            "balance": balance_data,
            "user": user,
            "users": users_by_id,
        },
    )
