"""Settlement routes for the monthly settlement workflow."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.adapters.sqlalchemy.queries.dashboard_queries import get_group_members
from app.adapters.sqlalchemy.queries.settlement_queries import (
    get_settlement_with_expenses,
    get_unsettled_expenses_grouped,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.errors import EmptySettlementError, StaleExpenseError
from app.domain.models import ExpensePublic
from app.domain.use_cases.settlements import calculate_settlement, confirm_settlement
from app.web.templates import setup_templates

router = APIRouter(tags=["settlements"])
templates = setup_templates("app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def _get_currency_symbol(default_currency: str) -> str:
    """Get currency symbol for a given currency code."""
    currency_symbols = {
        "EUR": "€",
        "USD": "$",
        "GBP": "£",
        "SEK": "kr",
    }
    return currency_symbols.get(default_currency, default_currency)


def _get_user_display_names(uow: UnitOfWork, group_id: int) -> dict[int, str]:
    """Get mapping of user IDs to display names."""
    members = get_group_members(uow.session, group_id)
    display_names = {}
    for member in members:
        user = uow.users.get_by_id(member.user_id)
        if user:
            display_names[member.user_id] = user.display_name
        else:
            display_names[member.user_id] = f"User {member.user_id}"
    return display_names


@router.get("/settlements/review", response_class=HTMLResponse)
async def settlement_review_page(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render settlement review page with unsettled expenses."""
    # Get user's group
    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

    # Get unsettled expenses grouped by week
    grouped_expenses = get_unsettled_expenses_grouped(uow.session, group.id)

    # Check for empty state
    total_unsettled = sum(len(expenses) for expenses in grouped_expenses.values())

    # Get display names
    display_names = _get_user_display_names(uow, group.id)

    return templates.TemplateResponse(
        request,
        "settlements/review.html",
        {
            "group": group,
            "grouped_expenses": grouped_expenses,
            "total_unsettled": total_unsettled,
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol(group.default_currency),
        },
    )


@router.post("/settlements/calculate-total", response_class=HTMLResponse)
async def calculate_settlement_total(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    expense_ids: list[int] = Form(default=[]),
):
    """HTMX endpoint to recalculate total based on selected expenses."""
    # Get user's group
    group = uow.groups.get_by_user_id(user_id)
    if not group:
        return ""

    # Fetch selected expenses
    expenses: list[ExpensePublic] = []
    for expense_id in expense_ids:
        expense = uow.expenses.get_by_id(expense_id)
        if expense:
            expenses.append(expense)

    # Get display names
    display_names = _get_user_display_names(uow, group.id)

    # Calculate settlement
    if expenses:
        calculation = calculate_settlement(expenses, display_names)
        total_amount = calculation.total_amount
        transfer_message = calculation.transfer_message
    else:
        total_amount = Decimal("0.00")
        transfer_message = "Select expenses to see total"

    return templates.TemplateResponse(
        request,
        "settlements/_review_summary.html",
        {
            "total_amount": total_amount,
            "transfer_message": transfer_message,
            "expense_count": len(expenses),
            "currency_symbol": _get_currency_symbol(group.default_currency),
        },
    )


@router.get("/settlements/confirm", response_class=HTMLResponse)
async def settlement_confirm_page(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    expense_ids: list[int] = Query(default=[]),
):
    """Render settlement confirmation page."""
    from app.domain.models import ExpenseStatus

    # Validate at least one expense selected
    if not expense_ids:
        return RedirectResponse(url="/settlements/review", status_code=303)

    # Get user's group
    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

    # Fetch and validate expenses
    expenses: list[ExpensePublic] = []
    error_message = None

    for expense_id in expense_ids:
        expense = uow.expenses.get_by_id(expense_id)
        if expense is None:
            error_message = f"Expense {expense_id} no longer exists"
            break
        if expense.status == ExpenseStatus.SETTLED:
            error_message = f"Expense {expense_id} has already been settled"
            break
        expenses.append(expense)

    if error_message:
        # Return to review page with error
        grouped_expenses = get_unsettled_expenses_grouped(uow.session, group.id)
        display_names = _get_user_display_names(uow, group.id)

        return templates.TemplateResponse(
            request,
            "settlements/review.html",
            {
                "error": error_message,
                "group": group,
                "grouped_expenses": grouped_expenses,
                "total_unsettled": sum(len(e) for e in grouped_expenses.values()),
                "display_names": display_names,
                "currency_symbol": _get_currency_symbol(group.default_currency),
            },
        )

    # Get display names
    display_names = _get_user_display_names(uow, group.id)

    # Calculate settlement
    calculation = calculate_settlement(expenses, display_names)

    return templates.TemplateResponse(
        request,
        "settlements/confirm.html",
        {
            "expenses": expenses,
            "expense_count": len(expenses),
            "total_amount": calculation.total_amount,
            "transfer_message": calculation.transfer_message,
            "transfer_from_user_id": calculation.transfer_from_user_id,
            "transfer_to_user_id": calculation.transfer_to_user_id,
            "expense_ids": expense_ids,
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol(group.default_currency),
        },
    )


@router.post("/settlements", response_class=HTMLResponse)
async def create_settlement(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    expense_ids: list[int] = Form(default=[]),
):
    """Create settlement and mark expenses as settled."""
    # Get user's group
    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

    # Get display names
    display_names = _get_user_display_names(uow, group.id)

    try:
        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=group.id,
                expense_ids=expense_ids,
                settled_by_id=user_id,
                user_display_names=display_names,
            )

        # Redirect to success page
        return RedirectResponse(
            url=f"/settlements/success?settlement_id={settlement.id}",
            status_code=303,
        )

    except (EmptySettlementError, StaleExpenseError) as e:
        # Return to review page with error
        grouped_expenses = get_unsettled_expenses_grouped(uow.session, group.id)
        return templates.TemplateResponse(
            request,
            "settlements/review.html",
            {
                "error": str(e),
                "group": group,
                "grouped_expenses": grouped_expenses,
                "total_unsettled": sum(len(e) for e in grouped_expenses.values()),
                "display_names": display_names,
                "currency_symbol": _get_currency_symbol(group.default_currency),
            },
        )


@router.get("/settlements/success", response_class=HTMLResponse)
async def settlement_success_page(
    request: Request,
    settlement_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render settlement success page."""
    settlement = uow.settlements.get_by_id(settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    # Get display names
    display_names = _get_user_display_names(uow, settlement.group_id)

    # Get expense count
    expense_ids = uow.settlements.get_expense_ids(settlement_id)

    return templates.TemplateResponse(
        request,
        "settlements/success.html",
        {
            "settlement": settlement,
            "expense_count": len(expense_ids),
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol("EUR"),
        },
    )


@router.get("/settlements", response_class=HTMLResponse)
async def settlement_history_page(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render settlement history list."""
    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

    settlements = uow.settlements.list_by_group(group.id)

    # Get display names
    display_names = _get_user_display_names(uow, group.id)

    # Build view models with expense counts
    settlement_view_models = []
    for settlement in settlements:
        expense_ids = uow.settlements.get_expense_ids(settlement.id)
        settlement_view_models.append(
            {
                "settlement": settlement,
                "expense_count": len(expense_ids),
                "from_name": display_names.get(settlement.transfer_from_user_id, "Unknown"),
                "to_name": display_names.get(settlement.transfer_to_user_id, "Unknown"),
            }
        )

    return templates.TemplateResponse(
        request,
        "settlements/index.html",
        {
            "settlements": settlement_view_models,
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol(group.default_currency),
        },
    )


@router.get("/settlements/{settlement_id}", response_class=HTMLResponse)
async def settlement_detail_page(
    request: Request,
    settlement_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render settlement detail with included expenses."""
    result = get_settlement_with_expenses(uow.session, settlement_id)
    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found")

    settlement, expenses = result

    # Get display names
    display_names = _get_user_display_names(uow, settlement.group_id)

    return templates.TemplateResponse(
        request,
        "settlements/detail.html",
        {
            "settlement": settlement,
            "expenses": expenses,
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol("EUR"),
        },
    )
