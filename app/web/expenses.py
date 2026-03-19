"""Expense creation routes for mobile and desktop."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from app.adapters.sqlalchemy.queries.dashboard_queries import get_group_members
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.use_cases.expenses import create_expense
from app.web.templates import setup_templates

router = APIRouter(tags=["expenses"])
templates = setup_templates("app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


class CreateExpenseForm(BaseModel):
    """Form validation for expense creation."""

    amount: Decimal = Field(gt=0, le=Decimal("1000000.00"), decimal_places=2)
    description: str = Field(default="", max_length=200)
    date: date
    payer_id: int
    currency: str = Field(default="EUR", max_length=3)
    split_type: str = Field(default="even")


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

    # Get user details for display names
    users_dict = {}
    for member in group_members:
        user_obj = uow.users.get_by_id(member.user_id)
        if user_obj:
            users_dict[member.user_id] = user_obj

    # Currency symbol mapping
    currency_symbols = {
        "EUR": "€",
        "USD": "$",
        "GBP": "£",
        "SEK": "kr",
    }

    # Pre-select current user as payer (simplify template logic)
    selected_payer_id = user_id

    return templates.TemplateResponse(
        "expenses/_capture_form_mobile.html",
        {
            "request": request,
            "group": group,
            "group_members": group_members,
            "users": users_dict,
            "current_user_id": user_id,
            "selected_payer_id": selected_payer_id,
            "today": date.today().isoformat(),
            "currency_symbol": currency_symbols.get(group.default_currency, group.default_currency),
        },
    )


@router.post("/expenses/create", response_class=HTMLResponse)
async def create_expense_endpoint(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    amount: str = Form(...),
    description: str = Form(""),
    date_str: str = Form(..., alias="date"),
    payer_id: int = Form(...),
    currency: str = Form("EUR"),
    split_type: str = Form("even"),
):
    """Create new expense (HTMX endpoint for mobile/desktop)."""

    # Get user's group
    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group = uow.groups.get_by_user_id(user_id)
    if not group:
        raise HTTPException(status_code=404, detail="User has no group")

    # Validate form
    errors = {}
    try:
        # Parse amount
        try:
            amount_decimal = Decimal(amount)
        except InvalidOperation, ValueError:
            errors["amount"] = "Invalid amount format"
            amount_decimal = None

        # Parse date
        try:
            expense_date = date.fromisoformat(date_str)
        except ValueError:
            errors["date"] = "Invalid date format"
            expense_date = None
        # Validate date is not in the future (HIGH-3)
        if expense_date and expense_date > date.today():
            errors["date"] = "Date cannot be in the future"

        # Validate payer_id is a member of the group (HIGH-4)
        if payer_id:
            group_members = get_group_members(uow.session, group.id)
            valid_payer_ids = {member.user_id for member in group_members}
            if payer_id not in valid_payer_ids:
                errors["payer_id"] = "Selected payer is not a member of your group"
        # Validate with Pydantic if no parse errors
        if not errors:
            form_data = CreateExpenseForm(
                amount=amount_decimal,
                description=description,
                date=expense_date,
                payer_id=payer_id,
                currency=currency,
                split_type=split_type,
            )
    except ValidationError as e:
        for error in e.errors():
            field = error["loc"][0]
            errors[field] = error["msg"]
        form_data = None

    # If validation errors, return form with errors (UX-DR24)
    if errors:
        group_members = get_group_members(uow.session, group.id)

        # Get user details
        users_dict = {}
        for member in group_members:
            user_obj = uow.users.get_by_id(member.user_id)
            if user_obj:
                users_dict[member.user_id] = user_obj

        currency_symbols = {
            "EUR": "€",
            "USD": "$",
            "GBP": "£",
            "SEK": "kr",
        }

        # Preserve payer_id from form data for error case
        selected_payer_id = payer_id if payer_id else user_id

        return templates.TemplateResponse(
            "expenses/_capture_form_mobile.html",
            {
                "request": request,
                "errors": errors,
                "form_data": {
                    "amount": amount,
                    "description": description,
                    "date": date_str,
                    "payer_id": payer_id,
                    "currency": currency,
                },
                "group": group,
                "group_members": group_members,
                "users": users_dict,
                "current_user_id": user_id,
                "selected_payer_id": selected_payer_id,
                "today": date.today().isoformat(),
                "currency_symbol": currency_symbols.get(
                    group.default_currency, group.default_currency
                ),
            },
            status_code=400,
        )

    # Create expense via use case
    with uow:
        expense = create_expense(
            uow=uow,
            group_id=group.id,
            amount=form_data.amount,
            description=form_data.description,
            date=form_data.date,
            creator_id=user_id,
            payer_id=form_data.payer_id,
            currency=form_data.currency,
        )

    # Get user details for display
    users_dict = {}
    group_members = get_group_members(uow.session, group.id)
    for member in group_members:
        user_obj = uow.users.get_by_id(member.user_id)
        if user_obj:
            users_dict[member.user_id] = user_obj

    # Return: new expense card
    response = templates.TemplateResponse(
        "expenses/_expense_card.html",
        {
            "request": request,
            "expense": expense,
            "users": users_dict,
            "current_user_id": user_id,
            "is_new": True,  # Trigger highlight animation
        },
    )

    # Add HTMX triggers for balance bar refresh and bottom sheet close
    response.headers["HX-Trigger"] = "expenseCreated"
    response.headers["HX-Trigger-After-Settle"] = "closeBottomSheet"

    return response
