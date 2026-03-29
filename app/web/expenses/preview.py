"""Mobile capture form and split preview endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.adapters.sqlalchemy.queries.dashboard_queries import get_all_users
from app.domain.errors import InvalidShareError
from app.domain.models import ExpensePublic, SplitType
from app.domain.use_cases.expenses import calculate_splits
from app.settings import settings
from app.web.expenses._shared import (
    CurrentUserId,
    UowDep,
    _get_currency_symbol,
    templates,
)
from app.web.form_parsing import parse_amount, parse_split_config

router = APIRouter(tags=["expenses"])


@router.get("/expenses/capture-form", response_class=HTMLResponse)
async def get_mobile_capture_form(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Load mobile expense capture form into bottom sheet."""
    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    all_users = get_all_users(uow.session)
    users_dict = {u.id: u for u in all_users}

    # Pre-select current user as payer (simplify template logic)
    selected_payer_id = user_id

    return templates.TemplateResponse(
        request,
        "expenses/_capture_form_mobile.html",
        {
            "users_list": all_users,
            "users": users_dict,
            "current_user_id": user_id,
            "selected_payer_id": selected_payer_id,
            "today": date.today().isoformat(),
            "currency_symbol": _get_currency_symbol(settings.DEFAULT_CURRENCY),
            "default_currency": settings.DEFAULT_CURRENCY,
        },
    )


@router.post("/expenses/split-preview", response_class=HTMLResponse)
async def get_split_preview(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    amount_str: Annotated[str, Form(alias="amount")] = "0",
    split_type: Annotated[str, Form()] = "even",
    split_config_json: Annotated[str, Form(alias="split_config")] = "{}",
    payer_id_str: Annotated[str, Form(alias="payer_id")] = "",
):
    """Calculate and return split preview HTML (HTMX endpoint).

    Receives form data via POST and returns calculated split amounts.
    Uses the same split strategies as the expense creation use case.
    """

    # Parse amount
    amount = parse_amount(amount_str) or Decimal("0")

    # Parse split config
    split_config = parse_split_config(split_config_json) or {}

    # Parse payer ID
    try:
        payer_id = int(payer_id_str) if payer_id_str else user_id
    except ValueError:
        payer_id = user_id

    # Get all users
    all_users = get_all_users(uow.session)
    member_ids = [u.id for u in all_users]
    users_dict = {u.id: u for u in all_users}

    # Create a mock expense for split calculation
    expense = ExpensePublic.model_construct(
        id=0,
        amount=amount or Decimal("0"),
        description="",
        date=date.today(),
        creator_id=user_id,
        payer_id=payer_id,
        currency=settings.DEFAULT_CURRENCY,
        split_type=SplitType.EVEN,
        status="PENDING",
        created_at=date.today(),
        updated_at=date.today(),
    )

    # Calculate splits using the appropriate strategy
    try:
        splits = calculate_splits(
            expense=expense,
            member_ids=member_ids,
            split_type=SplitType(split_type.upper()),
            split_config=split_config if split_type.upper() != "EVEN" else None,
        )
        error_message = None
    except InvalidShareError as e:
        splits = []
        error_message = str(e)

    return templates.TemplateResponse(
        request,
        "expenses/_split_preview.html",
        {
            "splits": splits,
            "users": users_dict,
            "error_message": error_message,
            "currency_symbol": _get_currency_symbol(settings.DEFAULT_CURRENCY),
        },
    )
