"""Mobile capture form and split preview endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.adapters.sqlalchemy.queries.dashboard_queries import get_group_members
from app.domain.errors import InvalidShareError
from app.domain.models import ExpensePublic, SplitType
from app.domain.use_cases.expenses import calculate_splits
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
    # Get group for current user
    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="User has no group")

    group_members = get_group_members(uow.session, group.id)

    # Get user details for display names (batch query)
    member_ids = [member.user_id for member in group_members]
    users = uow.users.get_by_ids(member_ids)
    users_dict = {u.id: u for u in users}

    # Pre-select current user as payer (simplify template logic)
    selected_payer_id = user_id

    return templates.TemplateResponse(
        request,
        "expenses/_capture_form_mobile.html",
        {
            "group": group,
            "group_members": group_members,
            "users": users_dict,
            "current_user_id": user_id,
            "selected_payer_id": selected_payer_id,
            "today": date.today().isoformat(),
            "currency_symbol": _get_currency_symbol(group.default_currency),
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

    # Get group members
    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="User has no group")

    members = get_group_members(uow.session, group.id)
    member_ids = [m.user_id for m in members]

    # Get user details for display names (batch query)
    users = uow.users.get_by_ids(member_ids)
    users_dict = {u.id: u for u in users}

    # Create a mock expense for split calculation
    expense = ExpensePublic.model_construct(
        id=0,
        group_id=group.id,
        amount=amount or Decimal("0"),
        description="",
        date=date.today(),
        creator_id=user_id,
        payer_id=payer_id,
        currency=group.default_currency,
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
            "currency_symbol": _get_currency_symbol(group.default_currency),
        },
    )
