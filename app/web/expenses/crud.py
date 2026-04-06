"""Create, update, and delete expense endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.adapters.sqlalchemy.queries.dashboard_queries import get_all_users
from app.domain.errors import InvalidShareError
from app.domain.use_cases.expenses import create_expense, delete_expense, update_expense
from app.settings import settings
from app.web.expenses._shared import (
    CreateExpenseForm,
    CurrentUserId,
    UowDep,
    UpdateExpenseForm,
    templates,
)
from app.web.filters import get_currency_symbol
from app.web.form_parsing import parse_amount, parse_date, parse_split_config

router = APIRouter(tags=["expenses"])


@router.post("/expenses/create", response_class=HTMLResponse)
async def create_expense_endpoint(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    amount: Annotated[str, Form()],
    date_str: Annotated[str, Form(alias="date")],
    payer_id: Annotated[int, Form()],
    description: Annotated[str, Form()] = "",
    currency: Annotated[str, Form()] = "EUR",
    split_type: Annotated[str, Form()] = "even",
    split_config_json: Annotated[str, Form(alias="split_config")] = "",
):
    """Create new expense (HTMX endpoint for mobile/desktop)."""

    # Get user
    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate form
    errors: dict[str, str] = {}
    try:
        # Parse amount
        amount_decimal = parse_amount(amount)
        if amount_decimal is None:
            errors["amount"] = "Invalid amount format"

        # Parse date
        expense_date = parse_date(date_str)
        if expense_date is None:
            errors["date"] = "Invalid date format"
        # Validate date is not in the future (HIGH-3)
        if expense_date and expense_date > date.today():
            errors["date"] = "Date cannot be in the future"

        # Validate payer_id is a valid user (HIGH-4)
        if payer_id:
            users = get_all_users(uow.session)
            valid_payer_ids = {u.id for u in users}
            if payer_id not in valid_payer_ids:
                errors["payer_id"] = "Selected payer is not a valid user"
        # Validate with Pydantic if no parse errors
        if not errors:
            assert amount_decimal is not None, "amount_decimal should not be None when no errors"
            assert expense_date is not None, "expense_date should not be None when no errors"
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
            field = str(error["loc"][0])
            errors[field] = error["msg"]
        form_data = None

    # Parse split_config from JSON
    split_config: dict[int, Decimal] | None = None
    if split_type.upper() != "EVEN" and split_config_json:
        split_config = parse_split_config(split_config_json)
        if split_config is None:
            errors["split_type"] = "Invalid split configuration"

    # If validation errors, return form with errors (UX-DR24)
    if errors or form_data is None:
        users = get_all_users(uow.session)
        users_dict: dict[int, Any] = {u.id: u for u in users}

        # Preserve payer_id from form data for error case
        selected_payer_id = payer_id if payer_id else user_id

        return templates.TemplateResponse(
            request,
            "expenses/_capture_form_mobile.html",
            {
                "errors": errors,
                "form_data": {
                    "amount": amount,
                    "description": description,
                    "date": date_str,
                    "payer_id": payer_id,
                    "currency": currency,
                },
                "users": users_dict,
                "users_list": users,
                "current_user_id": user_id,
                "selected_payer_id": selected_payer_id,
                "today": date.today().isoformat(),
                "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
                "default_currency": settings.DEFAULT_CURRENCY,
            },
            status_code=400,
        )

    # Get all users for split calculation
    users = get_all_users(uow.session)
    member_ids = [u.id for u in users]

    # Create expense via use case
    try:
        with uow:
            create_expense(
                uow=uow,
                amount=form_data.amount,
                description=form_data.description,
                date=form_data.date,
                creator_id=user_id,
                payer_id=form_data.payer_id,
                member_ids=member_ids,
                currency=form_data.currency,
                split_type=form_data.split_type,
                split_config=split_config,
            )
    except InvalidShareError as e:
        # Handle split validation errors
        users = get_all_users(uow.session)
        users_dict = {u.id: u for u in users}

        return templates.TemplateResponse(
            request,
            "expenses/_capture_form_mobile.html",
            {
                "errors": {"split_type": str(e)},
                "form_data": {
                    "amount": amount,
                    "description": description,
                    "date": date_str,
                    "payer_id": payer_id,
                    "currency": currency,
                },
                "users": users_dict,
                "users_list": users,
                "current_user_id": user_id,
                "selected_payer_id": payer_id if payer_id else user_id,
                "today": date.today().isoformat(),
                "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
                "default_currency": settings.DEFAULT_CURRENCY,
            },
            status_code=400,
        )

    # Redirect to expenses list page
    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = "/expenses"

    return response


@router.post("/expenses/{expense_id}/update", response_class=HTMLResponse)
async def update_expense_endpoint(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
    amount: Annotated[str, Form()] = "",
    description: Annotated[str, Form()] = "",
    date_str: Annotated[str, Form(alias="date")] = "",
    payer_id_str: Annotated[str, Form(alias="payer_id")] = "",
    currency: Annotated[str, Form()] = "",
    split_type_str: Annotated[str, Form(alias="split_type")] = "even",
    split_config_raw: Annotated[str, Form(alias="split_config")] = "",
):
    """Update expense (form submission)."""
    # Convert payer_id to int
    try:
        payer_id = int(payer_id_str) if payer_id_str else None
    except ValueError:
        payer_id = None

    # Authorization
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate form
    errors = {}
    try:
        # Parse amount
        amount_decimal = parse_amount(amount)
        if amount_decimal is None:
            errors["amount"] = "Invalid amount format"

        # Parse date
        expense_date = parse_date(date_str)
        if expense_date is None:
            errors["date"] = "Invalid date format"

        # Validate date is not in the future
        if expense_date and expense_date > date.today():
            errors["date"] = "Date cannot be in the future"

        # Validate payer_id is provided and is a valid user
        if payer_id is None:
            errors["payer_id"] = "Payer is required"
        else:
            users = get_all_users(uow.session)
            valid_payer_ids = {u.id for u in users}
            if payer_id not in valid_payer_ids:
                errors["payer_id"] = "Selected payer is not a valid user"

        # Validate with Pydantic if no parse errors
        if not errors:
            assert amount_decimal is not None, "amount_decimal should not be None when no errors"
            assert expense_date is not None, "expense_date should not be None when no errors"
            assert payer_id is not None, "payer_id should not be None when no errors"
            form_data = UpdateExpenseForm(
                amount=amount_decimal,
                description=description,
                date=expense_date,
                payer_id=payer_id,
                currency=currency,
                split_type=split_type_str if isinstance(split_type_str, str) else "even",
            )
    except ValidationError as e:
        for error in e.errors():
            field = str(error["loc"][0])
            errors[field] = error["msg"]
        form_data = None

    # Parse split_config from JSON
    split_config: dict[int, Decimal] | None = None
    if isinstance(split_type_str, str) and split_type_str.upper() != "EVEN" and split_config_raw:
        split_config = parse_split_config(split_config_raw)
        if split_config is None:
            errors["split_type"] = "Invalid split configuration"

    # If validation errors, return form with errors
    if errors or form_data is None:
        users = get_all_users(uow.session)
        users_dict = {u.id: u for u in users}

        return templates.TemplateResponse(
            request,
            "expenses/_edit_modal.html",
            {
                "errors": errors,
                "expense": expense,
                "users": users_dict,
                "users_list": users,
                "today": date.today().isoformat(),
                "csrf_token": getattr(request.state, "csrf_token", ""),
                "is_settled": expense.status == "SETTLED",
                "currency_symbol": get_currency_symbol(settings.DEFAULT_CURRENCY),
                "default_currency": settings.DEFAULT_CURRENCY,
                "split_config": {},
            },
            status_code=400,
        )

    # Update via use case
    with uow:
        # Get member IDs for split recalculation
        users = get_all_users(uow.session)
        member_ids = [u.id for u in users]

        update_expense(
            uow=uow,
            expense_id=expense_id,
            amount=form_data.amount,
            description=form_data.description,
            date=form_data.date,
            payer_id=form_data.payer_id,
            currency=form_data.currency,
            split_type=form_data.split_type,
            split_config=split_config,
            member_ids=member_ids,
        )

    # Redirect to expense list with success message
    return RedirectResponse(url="/expenses?updated=true", status_code=303)


@router.get("/expenses/{expense_id}/delete-confirm", response_class=HTMLResponse)
async def get_delete_confirmation(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Show delete confirmation modal via HTMX."""
    # Get expense and validate it exists
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Render confirmation modal
    return templates.TemplateResponse(
        request,
        "expenses/_delete_confirmation_modal.html",
        {
            "expense": expense,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/expenses/{expense_id}/delete")
async def delete_expense_route(
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Delete an expense and redirect to dashboard."""
    # Validate expense exists
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Execute delete use case (includes immutability check)
    with uow:
        delete_expense(
            uow=uow,
            expense_id=expense_id,
        )

    # Redirect to expense list (modal closes automatically, page refreshes)
    return RedirectResponse(url="/expenses", status_code=303)
