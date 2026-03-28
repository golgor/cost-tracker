"""Expense detail, collapse, and edit page endpoints."""

from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.adapters.sqlalchemy.queries.dashboard_queries import get_group_members
from app.web.expenses._shared import (
    CurrentUserId,
    UowDep,
    _get_currency_symbol,
    templates,
)

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

    # Authorization: user must be in the expense's group
    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group = uow.groups.get_by_user_id(user_id)
    if not group or group.id != expense.group_id:
        raise HTTPException(status_code=403, detail="Access denied")

    group_members = get_group_members(uow.session, group.id)

    # Get all users for display (batch query)
    member_ids = [m.user_id for m in group_members]
    users_list = uow.users.get_by_ids(member_ids)
    users_dict = {u.id: u for u in users_list}
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

    return templates.TemplateResponse(
        request,
        "expenses/_expense_card_expanded.html",
        {
            "expense": expense,
            "creator": creator,
            "payer": payer,
            "group_members": group_members,
            "users": users_dict,
            "current_user_id": user_id,
            "group": group,
            "is_settled": expense.status == "SETTLED",
            "splits_display": splits_display,
            "split_type_label": split_type_label,
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

    group = uow.groups.get_by_user_id(user_id)
    if not group or group.id != expense.group_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get user details for display (batch query)
    group_members = get_group_members(uow.session, group.id)
    member_ids = [m.user_id for m in group_members]
    users_list = uow.users.get_by_ids(member_ids)
    users_dict = {u.id: u for u in users_list}

    return templates.TemplateResponse(
        request,
        "expenses/_expense_card.html",
        {
            "expense": expense,
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

    group = uow.groups.get_by_user_id(user_id)
    if not group or group.id != expense.group_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get group members for paid-by selector
    group_members = get_group_members(uow.session, group.id)

    # Get user details for display (batch query)
    member_ids = [m.user_id for m in group_members]
    users_list = uow.users.get_by_ids(member_ids)
    users_dict = {u.id: u for u in users_list}

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
            "group": group,
            "group_members": group_members,
            "users": users_dict,
            "today": date.today().isoformat(),
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "is_settled": expense.status == "SETTLED",
            "currency_symbol": _get_currency_symbol(group.default_currency),
            "split_config": split_config_dict,
        },
    )
