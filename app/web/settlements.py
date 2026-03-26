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
from app.domain.balance import calculate_balances, minimize_transactions
from app.domain.errors import EmptySettlementError, StaleExpenseError
from app.domain.models import ExpensePublic, ExpenseStatus
from app.domain.splits import BalanceConfig
from app.domain.use_cases.settlements import confirm_settlement, format_transfer_message
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
    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

    grouped_expenses = get_unsettled_expenses_grouped(uow.session, group.id)
    total_unsettled = sum(len(expenses) for expenses in grouped_expenses.values())
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
            "total_amount": Decimal("0.00"),
            "transfer_message": "Select expenses to see total",
            "expense_count": 0,
            "csrf_token": getattr(request.state, "csrf_token", ""),
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
    cached_form = getattr(request.state, "_cached_form", None)
    if cached_form and not expense_ids:
        expense_ids_str = cached_form.getlist("expense_ids")
        expense_ids = [int(eid) for eid in expense_ids_str if eid.isdigit()]

    group = uow.groups.get_by_user_id(user_id)
    if not group:
        return ""

    expenses: list[ExpensePublic] = []
    for expense_id in expense_ids:
        expense = uow.expenses.get_by_id(expense_id)
        if expense:
            expenses.append(expense)

    display_names = _get_user_display_names(uow, group.id)

    if expenses:
        member_ids = list(display_names.keys())
        config = BalanceConfig()
        balances = calculate_balances(expenses, member_ids, config)
        domain_transactions = minimize_transactions(balances)
        total_amount = sum(tx.amount.amount for tx in domain_transactions)
        transfer_message = format_transfer_message(domain_transactions, display_names)
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
            "csrf_token": getattr(request.state, "csrf_token", ""),
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
    if not expense_ids:
        return RedirectResponse(url="/settlements/review", status_code=303)

    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

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

    display_names = _get_user_display_names(uow, group.id)

    if error_message:
        grouped_expenses = get_unsettled_expenses_grouped(uow.session, group.id)

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
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    member_ids = list(display_names.keys())
    config = BalanceConfig()
    balances = calculate_balances(expenses, member_ids, config)
    domain_transactions = minimize_transactions(balances)
    total_amount = sum(tx.amount.amount for tx in domain_transactions)
    transfer_message = format_transfer_message(domain_transactions, display_names)

    transactions = [
        {
            "from_user_id": tx.from_user_id,
            "to_user_id": tx.to_user_id,
            "from_name": display_names.get(tx.from_user_id, f"User {tx.from_user_id}"),
            "to_name": display_names.get(tx.to_user_id, f"User {tx.to_user_id}"),
            "amount": tx.amount.amount,
        }
        for tx in domain_transactions
    ]

    return templates.TemplateResponse(
        request,
        "settlements/confirm.html",
        {
            "expenses": expenses,
            "expense_count": len(expenses),
            "total_amount": total_amount,
            "transfer_message": transfer_message,
            "transactions": transactions,
            "expense_ids": expense_ids,
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol(group.default_currency),
            "csrf_token": getattr(request.state, "csrf_token", ""),
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
    cached_form = getattr(request.state, "_cached_form", None)
    if cached_form and not expense_ids:
        expense_ids_str = cached_form.getlist("expense_ids")
        expense_ids = [int(eid) for eid in expense_ids_str if eid.isdigit()]

    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

    display_names = _get_user_display_names(uow, group.id)
    member_ids = list(display_names.keys())

    try:
        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=group.id,
                expense_ids=expense_ids,
                settled_by_id=user_id,
                member_ids=member_ids,
            )

        return RedirectResponse(
            url=f"/settlements/success?settlement_id={settlement.id}",
            status_code=303,
        )

    except (EmptySettlementError, StaleExpenseError) as e:
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
                "csrf_token": getattr(request.state, "csrf_token", ""),
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

    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

    if settlement.group_id != group.id:
        raise HTTPException(status_code=403, detail="You don't have access to this settlement")

    display_names = _get_user_display_names(uow, settlement.group_id)
    expense_ids = uow.settlements.get_expense_ids(settlement_id)
    transactions = uow.settlements.get_transactions(settlement_id)

    transaction_views = [
        {
            "from_name": display_names.get(tx.from_user_id, f"User {tx.from_user_id}"),
            "to_name": display_names.get(tx.to_user_id, f"User {tx.to_user_id}"),
            "amount": tx.amount,
        }
        for tx in transactions
    ]

    return templates.TemplateResponse(
        request,
        "settlements/success.html",
        {
            "settlement": settlement,
            "expense_count": len(expense_ids),
            "transactions": transaction_views,
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol(group.default_currency),
            "csrf_token": getattr(request.state, "csrf_token", ""),
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
    display_names = _get_user_display_names(uow, group.id)

    settlement_view_models = []
    for settlement in settlements:
        expense_ids = uow.settlements.get_expense_ids(settlement.id)
        transactions = uow.settlements.get_transactions(settlement.id)

        total_amount = sum(tx.amount for tx in transactions)

        transaction_summaries = []
        for tx in transactions:
            transaction_summaries.append(
                {
                    "from_name": display_names.get(tx.from_user_id, f"User {tx.from_user_id}"),
                    "to_name": display_names.get(tx.to_user_id, f"User {tx.to_user_id}"),
                }
            )

        settlement_view_models.append(
            {
                "settlement": settlement,
                "expense_count": len(expense_ids),
                "total_amount": total_amount,
                "transactions": transaction_summaries,
                "transaction_count": len(transactions),
                "has_amount": total_amount > 0,
            }
        )

    return templates.TemplateResponse(
        request,
        "settlements/index.html",
        {
            "settlements": settlement_view_models,
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol(group.default_currency),
            "csrf_token": getattr(request.state, "csrf_token", ""),
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
    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="You are not a member of any group")

    result = get_settlement_with_expenses(uow.session, settlement_id)
    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found")

    settlement, expenses = result

    if settlement.group_id != group.id:
        raise HTTPException(status_code=403, detail="You don't have access to this settlement")

    display_names = _get_user_display_names(uow, settlement.group_id)
    transactions = uow.settlements.get_transactions(settlement_id)

    transaction_views = [
        {
            "from_name": display_names.get(tx.from_user_id, f"User {tx.from_user_id}"),
            "to_name": display_names.get(tx.to_user_id, f"User {tx.to_user_id}"),
            "amount": tx.amount,
        }
        for tx in transactions
    ]

    return templates.TemplateResponse(
        request,
        "settlements/detail.html",
        {
            "settlement": settlement,
            "expenses": expenses,
            "transactions": transaction_views,
            "display_names": display_names,
            "currency_symbol": _get_currency_symbol(group.default_currency),
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
