"""Expense detail, collapse, and edit page endpoints."""

from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.adapters.sqlalchemy.queries.dashboard_queries import (
    get_all_users,
    get_recurring_definition_names,
)
from app.settings import settings
from app.web.expenses._shared import (
    CurrentUserId,
    UowDep,
    _get_currency_symbol,
    templates,
)
from app.web.view_models import ExpenseCardViewModel

router = APIRouter(tags=["expenses"])


@router.get("/expenses/{expense_id}/detail", response_class=HTMLResponse)
async def get_expense_detail(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Load expense detail view (HTMX partial) - full expense card with detail."""
    # Get expense
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Authorization: verify user exists
    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    users = get_all_users(uow.session)
    users_dict = {u.id: u for u in users}
    creator = users_dict.get(expense.creator_id)
    payer = users_dict.get(expense.payer_id)

    # Fetch actual split rows and build view-model list
    raw_splits = uow.expenses.get_splits(expense.id)
    splits_display = [
        {
            "display_name": users_dict[s.user_id].display_name
            if s.user_id in users_dict
            else f"User {s.user_id}",
            "amount": s.amount,
        }
        for s in raw_splits
    ]
    split_type_label = expense.split_type.value.title()

    # Detect incomplete splits (e.g., expense created before partner joined)
    split_user_ids = {s.user_id for s in raw_splits}
    all_user_ids = set(users_dict.keys())
    has_incomplete_splits = split_user_ids != all_user_ids

    return templates.TemplateResponse(
        request,
        "expenses/_expense_card_expanded.html",
        {
            "expense": expense,
            "creator": creator,
            "payer": payer,
            "users": users_dict,
            "current_user_id": user_id,
            "is_settled": expense.status == "SETTLED",
            "splits_display": splits_display,
            "split_type_label": split_type_label,
            "has_incomplete_splits": has_incomplete_splits,
        },
    )


@router.get("/expenses/{expense_id}/collapse", response_class=HTMLResponse)
async def collapse_expense_detail(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Collapse expense detail back to card (HTMX partial)."""
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Authorization
    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all users for display
    users = get_all_users(uow.session)
    users_dict = {u.id: u for u in users}

    # Look up recurring definition name if applicable
    recurring_names: dict[int, str] = {}
    if expense.recurring_definition_id is not None:
        recurring_names = get_recurring_definition_names(
            uow.session, [expense.recurring_definition_id]
        )

    # Transform to view model for template
    payer = users_dict.get(expense.payer_id)
    payer_name = payer.display_name if payer else "Unknown User"
    currency_symbol = _get_currency_symbol(settings.DEFAULT_CURRENCY)
    rec_name = (
        recurring_names.get(expense.recurring_definition_id)
        if expense.recurring_definition_id
        else None
    )
    expense_vm = ExpenseCardViewModel.from_domain(
        expense=expense,
        payer_name=payer_name,
        currency_symbol=currency_symbol,
        current_user_id=user_id,
        recurring_name=rec_name,
    )

    return templates.TemplateResponse(
        request,
        "expenses/_expense_card.html",
        {
            "expense": expense_vm,
            "users": users_dict,
            "current_user_id": user_id,
            "is_new": False,
        },
    )


@router.get("/expenses/{expense_id}/edit", response_class=HTMLResponse)
async def edit_expense_page(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render expense edit page (full page, not inline per UX-DR26)."""
    # Get expense
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Authorization
    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get all users for paid-by selector
    users = get_all_users(uow.session)
    users_dict = {u.id: u for u in users}

    # Get current splits for pre-populating split config
    current_splits = uow.expenses.get_splits(expense.id)
    split_config_dict = {}
    for s in current_splits:
        if s.share_value is not None:
            split_config_dict[s.user_id] = str(s.share_value)

    return templates.TemplateResponse(
        request,
        "expenses/_edit_modal.html",
        {
            "expense": expense,
            "users": users_dict,
            "users_list": users,
            "today": date.today().isoformat(),
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "is_settled": expense.status == "SETTLED",
            "currency_symbol": _get_currency_symbol(settings.DEFAULT_CURRENCY),
            "default_currency": settings.DEFAULT_CURRENCY,
            "split_config": split_config_dict,
        },
    )
