"""Settlement routes for the monthly settlement workflow."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.adapters.sqlalchemy.queries.dashboard_queries import get_all_users
from app.adapters.sqlalchemy.queries.settlement_queries import (
    get_settlement_with_expenses,
    get_unsettled_expenses_grouped,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.errors import EmptySettlementError, SettlementError, StaleExpenseError
from app.domain.models import UserPublic
from app.domain.use_cases.settlements import (
    confirm_settlement,
    format_transfer_message,
    preview_settlement,
)
from app.settings import settings
from app.web.filters import get_currency_symbol
from app.web.templates import setup_templates
from app.web.view_models import SettlementHistoryViewModel

router = APIRouter(tags=["settlements"])
templates = setup_templates("app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def _get_user_display_names(users: list[UserPublic]) -> dict[int, str]:
    """Get mapping of user IDs to display names."""
    return {u.id: u.display_name for u in users}


@router.get("/settlements/review", response_class=HTMLResponse)
async def settlement_review_page(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render settlement review page with unsettled expenses."""
    users = get_all_users(uow.session)
    grouped_expenses = get_unsettled_expenses_grouped(uow.session)
    total_unsettled = sum(len(expenses) for expenses in grouped_expenses.values())
    display_names = _get_user_display_names(users)

    return templates.TemplateResponse(
        request,
        "settlements/review.html",
        {
            "grouped_expenses": grouped_expenses,
            "total_unsettled": total_unsettled,
            "display_names": display_names,
            "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
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
    expense_ids: Annotated[list[int] | None, Form()] = None,
):
    """HTMX endpoint to recalculate total based on selected expenses."""
    if expense_ids is None:
        expense_ids = []

    users = get_all_users(uow.session)
    display_names = _get_user_display_names(users)

    if expense_ids:
        member_ids = [u.id for u in users]
        try:
            transactions, _balances = preview_settlement(uow, expense_ids, member_ids)
            total_amount = sum(tx.amount.amount for tx in transactions)
            transfer_message = format_transfer_message(transactions, display_names)
        except SettlementError, StaleExpenseError:
            total_amount = Decimal("0.00")
            transfer_message = "Some expenses are no longer available"
    else:
        total_amount = Decimal("0.00")
        transfer_message = "Select expenses to see total"

    return templates.TemplateResponse(
        request,
        "settlements/_review_summary.html",
        {
            "total_amount": total_amount,
            "transfer_message": transfer_message,
            "expense_count": len(expense_ids),
            "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/settlements/confirm", response_class=HTMLResponse)
async def settlement_confirm_page(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    expense_ids: Annotated[list[int] | None, Form()] = None,
):
    """Render settlement confirmation page."""
    if not expense_ids:
        return RedirectResponse(url="/settlements/review", status_code=303)

    users = get_all_users(uow.session)
    display_names = _get_user_display_names(users)
    member_ids = [u.id for u in users]

    try:
        domain_transactions, _balances = preview_settlement(uow, expense_ids, member_ids)
    except (SettlementError, StaleExpenseError) as e:
        grouped_expenses = get_unsettled_expenses_grouped(uow.session)
        return templates.TemplateResponse(
            request,
            "settlements/review.html",
            {
                "error": str(e),
                "grouped_expenses": grouped_expenses,
                "total_unsettled": sum(len(exps) for exps in grouped_expenses.values()),
                "display_names": display_names,
                "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
                "csrf_token": getattr(request.state, "csrf_token", ""),
            },
        )

    # Load expenses for display (already validated by preview_settlement)
    expenses = [uow.expenses.get_by_id(eid) for eid in expense_ids]

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
            "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/settlements", response_class=HTMLResponse)
async def create_settlement(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    expense_ids: Annotated[list[int] | None, Form()] = None,
):
    """Create settlement and mark expenses as settled."""
    if expense_ids is None:
        expense_ids = []

    users = get_all_users(uow.session)
    display_names = _get_user_display_names(users)
    member_ids = [u.id for u in users]

    try:
        with uow:
            settlement = confirm_settlement(
                uow,
                expense_ids=expense_ids,
                settled_by_id=user_id,
                member_ids=member_ids,
            )

        return RedirectResponse(
            url=f"/settlements/success?settlement_id={settlement.id}",
            status_code=303,
        )

    except (EmptySettlementError, StaleExpenseError) as e:
        grouped_expenses = get_unsettled_expenses_grouped(uow.session)
        return templates.TemplateResponse(
            request,
            "settlements/review.html",
            {
                "error": str(e),
                "grouped_expenses": grouped_expenses,
                "total_unsettled": sum(len(exps) for exps in grouped_expenses.values()),
                "display_names": display_names,
                "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
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

    users = get_all_users(uow.session)
    display_names = _get_user_display_names(users)
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
            "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
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
    users = get_all_users(uow.session)
    settlements = uow.settlements.list_all()
    display_names = _get_user_display_names(users)

    settlement_view_models = []
    for settlement in settlements:
        expense_ids = uow.settlements.get_expense_ids(settlement.id)
        transactions = uow.settlements.get_transactions(settlement.id)

        settlement_view_models.append(
            SettlementHistoryViewModel.from_domain(
                settlement=settlement,
                expense_count=len(expense_ids),
                transactions=transactions,
                display_names=display_names,
            )
        )

    return templates.TemplateResponse(
        request,
        "settlements/index.html",
        {
            "settlements": settlement_view_models,
            "display_names": display_names,
            "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
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
    result = get_settlement_with_expenses(uow.session, settlement_id)
    if not result:
        raise HTTPException(status_code=404, detail="Settlement not found")

    settlement, expenses = result

    users = get_all_users(uow.session)
    display_names = _get_user_display_names(users)
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
            "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
