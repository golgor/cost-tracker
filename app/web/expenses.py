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
        request,
        "expenses/_capture_form_mobile.html",
        {
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
        request,
        "expenses/_expense_card.html",
        {
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

    # Get creator and payer names
    creator = uow.users.get_by_id(expense.creator_id)
    payer = uow.users.get_by_id(expense.payer_id)
    group_members = get_group_members(uow.session, group.id)

    # Get all users for display
    users_dict = {}
    for member in group_members:
        user_obj = uow.users.get_by_id(member.user_id)
        if user_obj:
            users_dict[member.user_id] = user_obj

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

    # Get user details for display
    users_dict = {}
    group_members = get_group_members(uow.session, group.id)
    for member in group_members:
        user_obj = uow.users.get_by_id(member.user_id)
        if user_obj:
            users_dict[member.user_id] = user_obj

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

    # Get user details for display
    users_dict = {}
    for member in group_members:
        user_obj = uow.users.get_by_id(member.user_id)
        if user_obj:
            users_dict[member.user_id] = user_obj

    return templates.TemplateResponse(
        request,
        "expenses/edit.html",
        {
            "expense": expense,
            "group": group,
            "group_members": group_members,
            "users": users_dict,
            "today": date.today().isoformat(),
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "is_settled": expense.status == "SETTLED",
        },
    )


class UpdateExpenseForm(BaseModel):
    """Form validation for expense updates."""

    amount: Decimal = Field(gt=0, le=Decimal("1000000.00"))
    description: str = Field(default="", max_length=200)
    date: date
    payer_id: int
    currency: str = Field(max_length=3)


@router.post("/expenses/{expense_id}/update", response_class=HTMLResponse)
async def update_expense_endpoint(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Update expense (form submission)."""
    # Parse form data (use cached form from CSRF middleware if available)
    if hasattr(request.state, "_cached_form"):
        form = request.state._cached_form
    else:
        form = await request.form()
    
    amount = form.get("amount", "")
    description = form.get("description", "")
    date_str = form.get("date", "")
    payer_id_str = form.get("payer_id", "")
    currency = form.get("currency", "")
    
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

    group = uow.groups.get_by_user_id(user_id)
    if not group or group.id != expense.group_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Validate form
    errors = {}
    try:
        # Parse amount
        try:
            amount_decimal = Decimal(amount)
        except (InvalidOperation, ValueError):
            errors["amount"] = "Invalid amount format"
            amount_decimal = None

        # Parse date
        try:
            expense_date = date.fromisoformat(date_str)
        except ValueError:
            errors["date"] = "Invalid date format"
            expense_date = None

        # Validate date is not in the future
        if expense_date and expense_date > date.today():
            errors["date"] = "Date cannot be in the future"

        # Validate payer_id is a member of the group
        if payer_id:
            group_members = get_group_members(uow.session, group.id)
            valid_payer_ids = {member.user_id for member in group_members}
            if payer_id not in valid_payer_ids:
                errors["payer_id"] = "Selected payer is not a member of your group"

        # Validate with Pydantic if no parse errors
        if not errors:
            form_data = UpdateExpenseForm(
                amount=amount_decimal,
                description=description,
                date=expense_date,
                payer_id=payer_id,
                currency=currency,
            )
    except ValidationError as e:
        for error in e.errors():
            field = error["loc"][0]
            errors[field] = error["msg"]
        form_data = None

    # If validation errors, return form with errors
    if errors:
        group_members = get_group_members(uow.session, group.id)

        # Get user details
        users_dict = {}
        for member in group_members:
            user_obj = uow.users.get_by_id(member.user_id)
            if user_obj:
                users_dict[member.user_id] = user_obj

        return templates.TemplateResponse(
            request,
            "expenses/edit.html",
            {
                "errors": errors,
                "expense": expense,
                "group": group,
                "group_members": group_members,
                "users": users_dict,
                "today": date.today().isoformat(),
                "csrf_token": getattr(request.state, "csrf_token", ""),
                "is_settled": expense.status == "SETTLED",
            },
            status_code=400,
        )

    # Update via use case
    from app.domain.use_cases.expenses import update_expense

    with uow:
        update_expense(
            uow=uow,
            expense_id=expense_id,
            amount=form_data.amount,
            description=form_data.description,
            date=form_data.date,
            payer_id=form_data.payer_id,
            currency=form_data.currency,
            actor_id=user_id,
        )

    # Redirect to dashboard with success message
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/?updated=true", status_code=303)
