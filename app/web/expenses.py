"""Expense creation routes for mobile and desktop."""

import contextlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from app.adapters.sqlalchemy.queries.dashboard_queries import (
    calculate_balance,
    get_filtered_expenses,
    get_group_members,
    get_recurring_definition_names,
    get_this_month_total,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.errors import DomainError, InvalidShareError
from app.domain.models import ExpensePublic, ExpenseStatus, SplitType, UserPublic
from app.domain.splits import (
    EvenSplitStrategy,
    ExactSplitStrategy,
    PercentageSplitStrategy,
    SharesSplitStrategy,
)
from app.domain.use_cases.expenses import create_expense
from app.web.templates import setup_templates

router = APIRouter(tags=["expenses"])
templates = setup_templates("app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]


def _parse_date_filters(
    date_from: str | None, date_to: str | None
) -> tuple[date | None, date | None]:
    """Parse date filter strings into date objects, ignoring invalid dates."""
    date_from_parsed = None
    date_to_parsed = None

    if date_from:
        with contextlib.suppress(ValueError):
            date_from_parsed = date.fromisoformat(date_from)

    if date_to:
        with contextlib.suppress(ValueError):
            date_to_parsed = date.fromisoformat(date_to)

    return date_from_parsed, date_to_parsed


def _build_expense_count_message(expense_count: int, search_query: str | None = None) -> str:
    """Build human-readable expense count message."""
    if search_query:
        if expense_count == 0:
            return f'No expenses match "{search_query}"'
        elif expense_count == 1:
            return f'Showing 1 result for "{search_query}"'
        else:
            return f'Showing {expense_count} results for "{search_query}"'
    if expense_count == 0:
        return "No expenses"
    elif expense_count == 1:
        return "1 expense"
    else:
        return f"{expense_count} expenses"


def _has_active_expense_filters(
    date_from: str | None, date_to: str | None, payer_id: int | None
) -> bool:
    """Check if any expense filters are active."""
    return any([date_from, date_to, payer_id])


def _get_currency_symbol(default_currency: str) -> str:
    """Get currency symbol for a given currency code."""
    currency_symbols = {
        "EUR": "€",
        "USD": "$",
        "GBP": "£",
        "SEK": "kr",
    }
    return currency_symbols.get(default_currency, default_currency)


def _render_expense_notes_section(
    request: Request,
    expense_id: int,
    user_id: int,
    uow: UnitOfWork,
) -> HTMLResponse:
    """Render expense notes section HTML with context.

    Fetches notes, builds users dict from note authors and group members,
    and returns TemplateResponse with csrf_token for HTMX forms.
    """
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    group = uow.groups.get_by_id(expense.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    notes = uow.expenses.list_notes_by_expense(expense_id)
    users_dict: dict[int, UserPublic] = {}

    for note in notes:
        author = uow.users.get_by_id(note.author_id)
        if author:
            users_dict[note.author_id] = author

    group_members = get_group_members(uow.session, group.id)
    for member in group_members:
        user_obj = uow.users.get_by_id(member.user_id)
        if user_obj:
            users_dict[member.user_id] = user_obj

    return templates.TemplateResponse(
        request,
        "expenses/_expense_notes.html",
        {
            "notes": notes,
            "users": users_dict,
            "current_user_id": user_id,
            "expense": expense,
            "is_settled": expense.status == ExpenseStatus.SETTLED,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


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
):
    """Calculate and return split preview HTML (HTMX endpoint).

    Receives form data via POST and returns calculated split amounts.
    Uses the same split strategies as the expense creation use case.
    """
    # Parse form data (use cached form from CSRF middleware if available)
    if hasattr(request.state, "_cached_form"):
        form = request.state._cached_form
    else:
        form = await request.form()

    amount_str = form.get("amount", "0")
    split_type = form.get("split_type", "even")
    split_config_json = form.get("split_config", "{}")
    payer_id_str = form.get("payer_id", "")

    # Validate form values are strings (not UploadFile)
    if not isinstance(amount_str, str):
        raise HTTPException(status_code=400, detail="Invalid form field: amount")
    if not isinstance(split_type, str):
        raise HTTPException(status_code=400, detail="Invalid form field: split_type")
    if not isinstance(split_config_json, str):
        raise HTTPException(status_code=400, detail="Invalid form field: split_config")
    if not isinstance(payer_id_str, str):
        raise HTTPException(status_code=400, detail="Invalid form field: payer_id")

    # Parse amount
    try:
        amount = Decimal(amount_str.replace(",", "."))
    except InvalidOperation, ValueError:
        amount = Decimal("0")

    # Parse split config
    try:
        config_data = json.loads(split_config_json) if split_config_json else {}
        split_config = {int(k): Decimal(str(v)) for k, v in config_data.items()}
    except json.JSONDecodeError, ValueError:
        split_config = {}

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

    # Get user details for display names
    users_dict = {}
    for member in members:
        user_obj = uow.users.get_by_id(member.user_id)
        if user_obj:
            users_dict[member.user_id] = user_obj

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
        splits = _calculate_splits_backend(
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


def _calculate_splits_backend(
    expense: ExpensePublic,
    member_ids: list[int],
    split_type: SplitType,
    split_config: dict[int, Decimal] | None,
) -> list[tuple[int, Decimal, Decimal | None]]:
    """Calculate split amounts using backend strategies.

    Returns list of (user_id, amount, share_value) tuples.
    """
    if split_type == SplitType.EVEN:
        strategy = EvenSplitStrategy()
        shares = strategy.calculate_shares(expense, member_ids)
        return [(user_id, share.amount, None) for user_id, share in shares.items()]

    if split_type == SplitType.SHARES:
        if not split_config:
            raise InvalidShareError("Shares split requires share counts")
        strategy = SharesSplitStrategy()
        shares = strategy.calculate_shares(expense, member_ids, split_config)
        return [
            (user_id, share.amount, split_config.get(user_id)) for user_id, share in shares.items()
        ]

    if split_type == SplitType.PERCENTAGE:
        if not split_config:
            raise InvalidShareError("Percentage split requires percentages")
        strategy = PercentageSplitStrategy()
        shares = strategy.calculate_shares(expense, member_ids, split_config)
        return [
            (user_id, share.amount, split_config.get(user_id)) for user_id, share in shares.items()
        ]

    if split_type == SplitType.EXACT:
        if not split_config:
            raise InvalidShareError("Exact split requires exact amounts")
        strategy = ExactSplitStrategy()
        shares = strategy.calculate_shares(expense, member_ids, split_config)
        return [(user_id, share.amount, None) for user_id, share in shares.items()]

    raise DomainError(f"Unknown split type: {split_type}")


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
    split_config_json: str = Form("", alias="split_config"),
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
    errors: dict[str, str] = {}
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
        try:
            config_data = json.loads(split_config_json) if split_config_json else {}
            split_config = {int(k): Decimal(str(v)) for k, v in config_data.items()}
        except (json.JSONDecodeError, ValueError):
            errors["split_type"] = "Invalid split configuration"

    # If validation errors, return form with errors (UX-DR24)
    if errors or form_data is None:
        group_members = get_group_members(uow.session, group.id)

        # Get user details
        users_dict: dict[int, Any] = {}
        for member in group_members:
            user_obj = uow.users.get_by_id(member.user_id)
            if user_obj:
                users_dict[member.user_id] = user_obj

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
                "currency_symbol": _get_currency_symbol(group.default_currency),
            },
            status_code=400,
        )

    # Get group members for split calculation
    group_members = get_group_members(uow.session, group.id)
    member_ids = [member.user_id for member in group_members]

    # Create expense via use case
    try:
        with uow:
            create_expense(
                uow=uow,
                group_id=group.id,
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
        group_members = get_group_members(uow.session, group.id)
        users_dict = {}
        for member in group_members:
            user_obj = uow.users.get_by_id(member.user_id)
            if user_obj:
                users_dict[member.user_id] = user_obj

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
                "group": group,
                "group_members": group_members,
                "users": users_dict,
                "current_user_id": user_id,
                "selected_payer_id": payer_id if payer_id else user_id,
                "today": date.today().isoformat(),
                "currency_symbol": _get_currency_symbol(group.default_currency),
            },
            status_code=400,
        )

    # Get user details for display
    users_dict = {}
    group_members = get_group_members(uow.session, group.id)
    for member in group_members:
        user_obj = uow.users.get_by_id(member.user_id)
        if user_obj:
            users_dict[member.user_id] = user_obj

    # Redirect to expenses list page
    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Redirect"] = "/expenses"

    return response


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_list(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    payer_id: int | None = Query(None),
    search_query: str | None = Query(None),
):
    """Dedicated expenses list page with filtering.

    Shows all expenses for the group with filter controls.
    Distinct from dashboard which shows recent expenses only.
    """
    with uow:
        # Get user and group
        user = uow.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        group = uow.groups.get_by_user_id(user_id)
        if not group:
            raise HTTPException(status_code=404, detail="User has no group")

        # Parse date filters and get filtered expenses
        date_from_parsed, date_to_parsed = _parse_date_filters(date_from, date_to)
        unsettled_expenses = get_filtered_expenses(
            uow.session,
            group.id,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            status="PENDING",
            search_query=search_query or None,
        )
        settled_expenses = get_filtered_expenses(
            uow.session,
            group.id,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            status="SETTLED",
            search_query=search_query or None,
        )

        # Get balance data (filtered when filters are active)
        balance_data = calculate_balance(
            uow.session,
            group.id,
            user_id,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            search_query=search_query.strip() if search_query else None,
        )

        # Get this month total
        this_month_total = get_this_month_total(uow.session, group.id)

        # Get group members for display and filters
        members = get_group_members(uow.session, group.id)

        # Get user details for expense cards
        member_user_ids = [m.user_id for m in members]
        users_by_id = {}
        for uid in member_user_ids:
            user_obj = uow.users.get_by_id(uid)
            if user_obj:
                users_by_id[uid] = user_obj

        # Collect recurring definition IDs for name lookup
        all_expenses = unsettled_expenses + settled_expenses
        definition_ids = [
            e.recurring_definition_id for e in all_expenses if e.recurring_definition_id is not None
        ]
        recurring_names = get_recurring_definition_names(uow.session, definition_ids)

    # Result count message
    total_expenses = len(unsettled_expenses) + len(settled_expenses)
    active_search = search_query.strip() if search_query else None
    count_message = _build_expense_count_message(total_expenses, active_search)

    # Check if any filters are active
    has_active_filters = _has_active_expense_filters(date_from, date_to, payer_id)

    return templates.TemplateResponse(
        request,
        "expenses/index.html",
        {
            "user": user,
            "group": group,
            "unsettled_expenses": unsettled_expenses,
            "settled_expenses": settled_expenses,
            "balance": balance_data,
            "this_month_total": this_month_total,
            "group_members": members,
            "users": users_by_id,
            "current_user_id": user_id,
            "today": date.today().isoformat(),
            "currency_symbol": _get_currency_symbol(group.default_currency),
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "count_message": count_message,
            "has_active_filters": has_active_filters,
            "has_active_search": bool(active_search),
            "search_query": active_search or "",
            "recurring_names": recurring_names,
            # Filter values for form persistence
            "filter_date_from": date_from or "",
            "filter_date_to": date_to or "",
            "filter_payer_id": payer_id or "",
        },
    )


@router.get("/expenses/filtered", response_class=HTMLResponse)
async def expenses_filtered(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    payer_id: int | None = Query(None),
    search_query: str | None = Query(None),
):
    """HTMX endpoint for filtered expense feed partial.

    Returns only the expense feed section for HTMX partial swap.
    """
    with uow:
        # Get user's group
        group = uow.groups.get_by_user_id(user_id)
        if not group:
            raise HTTPException(status_code=404, detail="User has no group")

        # Parse date filters and get filtered expenses
        date_from_parsed, date_to_parsed = _parse_date_filters(date_from, date_to)
        active_search = search_query.strip() if search_query else None
        unsettled_expenses = get_filtered_expenses(
            uow.session,
            group.id,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            status="PENDING",
            search_query=active_search,
        )
        settled_expenses = get_filtered_expenses(
            uow.session,
            group.id,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            status="SETTLED",
            search_query=active_search,
        )

        # Get user details
        members = get_group_members(uow.session, group.id)
        users_by_id = {}
        for member in members:
            user_obj = uow.users.get_by_id(member.user_id)
            if user_obj:
                users_by_id[member.user_id] = user_obj

        # Collect recurring definition IDs for name lookup
        all_expenses = unsettled_expenses + settled_expenses
        definition_ids = [
            e.recurring_definition_id for e in all_expenses if e.recurring_definition_id is not None
        ]
        recurring_names = get_recurring_definition_names(uow.session, definition_ids)

    # Result count message
    total_expenses = len(unsettled_expenses) + len(settled_expenses)
    count_message = _build_expense_count_message(total_expenses, active_search)

    # Check if filters are active
    has_active_filters = _has_active_expense_filters(date_from, date_to, payer_id)

    return templates.TemplateResponse(
        request,
        "expenses/_expense_feed.html",
        {
            "unsettled_expenses": unsettled_expenses,
            "settled_expenses": settled_expenses,
            "users": users_by_id,
            "current_user_id": user_id,
            "count_message": count_message,
            "has_active_filters": has_active_filters,
            "has_active_search": bool(active_search),
            "search_query": active_search or "",
            "currency_symbol": _get_currency_symbol(group.default_currency),
            "recurring_names": recurring_names,
        },
    )


@router.get("/expenses/balance", response_class=HTMLResponse)
async def expenses_balance(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    payer_id: int | None = Query(None),
    search_query: str | None = Query(None),
):
    """HTMX endpoint for filtered balance bar partial."""
    with uow:
        user = uow.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        group = uow.groups.get_by_user_id(user_id)
        if not group:
            raise HTTPException(status_code=404, detail="User has no group")

        date_from_parsed, date_to_parsed = _parse_date_filters(date_from, date_to)

        balance_data = calculate_balance(
            uow.session,
            group.id,
            user_id,
            date_from=date_from_parsed,
            date_to=date_to_parsed,
            payer_id=payer_id,
            search_query=search_query.strip() if search_query else None,
        )

        members = get_group_members(uow.session, group.id)
        users_by_id = {}
        for member in members:
            user_obj = uow.users.get_by_id(member.user_id)
            if user_obj:
                users_by_id[member.user_id] = user_obj

    return templates.TemplateResponse(
        request,
        "expenses/_balance_bar.html",
        {
            "balance": balance_data,
            "user": user,
            "users": users_by_id,
        },
    )


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


class UpdateExpenseForm(BaseModel):
    """Form validation for expense updates."""

    amount: Decimal = Field(gt=0, le=Decimal("1000000.00"))
    description: str = Field(default="", max_length=200)
    date: date
    payer_id: int
    currency: str = Field(max_length=3)
    split_type: str = Field(default="even")


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
    split_type_str = form.get("split_type", "even")
    split_config_raw = form.get("split_config", "")

    # Validate form values are strings (not UploadFile)
    if not isinstance(amount, str):
        raise HTTPException(status_code=400, detail="Invalid form field: amount")
    if not isinstance(description, str):
        raise HTTPException(status_code=400, detail="Invalid form field: description")
    if not isinstance(date_str, str):
        raise HTTPException(status_code=400, detail="Invalid form field: date")
    if not isinstance(payer_id_str, str):
        raise HTTPException(status_code=400, detail="Invalid form field: payer_id")
    if not isinstance(currency, str):
        raise HTTPException(status_code=400, detail="Invalid form field: currency")

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

        # Validate payer_id is provided and is a member of the group
        if payer_id is None:
            errors["payer_id"] = "Payer is required"
        else:
            group_members = get_group_members(uow.session, group.id)
            valid_payer_ids = {member.user_id for member in group_members}
            if payer_id not in valid_payer_ids:
                errors["payer_id"] = "Selected payer is not a member of your group"

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
        try:
            config_str = split_config_raw if isinstance(split_config_raw, str) else ""
            config_data = json.loads(config_str) if config_str else {}
            split_config = {int(k): Decimal(str(v)) for k, v in config_data.items()}
        except (json.JSONDecodeError, ValueError):
            errors["split_type"] = "Invalid split configuration"

    # If validation errors, return form with errors
    if errors or form_data is None:
        group_members = get_group_members(uow.session, group.id)

        # Get user details
        users_dict = {}
        for member in group_members:
            user_obj = uow.users.get_by_id(member.user_id)
            if user_obj:
                users_dict[member.user_id] = user_obj

        return templates.TemplateResponse(
            request,
            "expenses/_edit_modal.html",
            {
                "errors": errors,
                "expense": expense,
                "group": group,
                "group_members": group_members,
                "users": users_dict,
                "today": date.today().isoformat(),
                "csrf_token": getattr(request.state, "csrf_token", ""),
                "is_settled": expense.status == "SETTLED",
                "currency_symbol": _get_currency_symbol(group.default_currency),
                "split_config": {},
            },
            status_code=400,
        )

    # Update via use case
    from app.domain.use_cases.expenses import update_expense

    with uow:
        # Get member IDs for split recalculation
        group = uow.groups.get_by_user_id(user_id)
        group_members = get_group_members(uow.session, group.id) if group else []
        member_ids = [m.user_id for m in group_members]

        update_expense(
            uow=uow,
            expense_id=expense_id,
            amount=form_data.amount,
            description=form_data.description,
            date=form_data.date,
            payer_id=form_data.payer_id,
            currency=form_data.currency,
            actor_id=user_id,
            split_type=form_data.split_type,
            split_config=split_config,
            member_ids=member_ids,
        )

    # Redirect to expense list with success message
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/expenses?updated=true", status_code=303)


@router.get("/expenses/{expense_id}/delete-confirm", response_class=HTMLResponse)
async def get_delete_confirmation(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Show delete confirmation modal via HTMX."""
    # Get expense and validate authorization
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Verify user has access to this expense's group
    group = uow.groups.get_by_user_id(user_id)
    if not group or group.id != expense.group_id:
        raise HTTPException(status_code=403, detail="Access denied")

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
    from fastapi.responses import RedirectResponse

    from app.domain.use_cases.expenses import delete_expense

    # Authorization check - get expense and validate group membership
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    user = uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group = uow.groups.get_by_user_id(user_id)
    if not group or group.id != expense.group_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Execute delete use case (includes immutability check)
    with uow:
        delete_expense(
            uow=uow,
            expense_id=expense_id,
            actor_id=user_id,
        )

    # Redirect to expense list (modal closes automatically, page refreshes)
    return RedirectResponse(url="/expenses", status_code=303)


@router.get("/expenses/{expense_id}/notes", response_class=HTMLResponse)
async def get_expense_notes(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Get expense notes section (HTMX endpoint).

    Returns notes section HTML.
    """
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    group = uow.groups.get_by_user_id(user_id)
    if not group or group.id != expense.group_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return _render_expense_notes_section(request, expense_id, user_id, uow)


@router.post("/expenses/{expense_id}/notes", response_class=HTMLResponse)
async def add_expense_note(
    request: Request,
    expense_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Add a note to an expense (HTMX endpoint).

    Returns updated notes section HTML.
    """
    # Get form data
    form_data = await request.form()
    content = str(form_data.get("content", "")).strip()

    if not content:
        return HTMLResponse(
            content="<div class='text-red-600 text-sm'>Note cannot be empty</div>", status_code=400
        )

    # Get expense and validate
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

    # Cannot add notes to settled expenses
    if expense.status == ExpenseStatus.SETTLED:
        return HTMLResponse(
            content="<div class='text-red-600 text-sm'>Cannot add notes to settled expenses</div>",
            status_code=400,
        )

    # Create note
    from app.domain.models import ExpenseNotePublic

    with uow:
        note = ExpenseNotePublic(
            id=0,
            expense_id=expense_id,
            author_id=user_id,
            content=content,
            created_at=datetime.now(),  # Placeholder, will be set by database
            updated_at=datetime.now(),  # Placeholder, will be set by database
        )
        uow.expenses.save_note(note, actor_id=user_id)

    return _render_expense_notes_section(request, expense_id, user_id, uow)


@router.get("/expenses/notes/{note_id}/edit-form", response_class=HTMLResponse)
async def edit_expense_note_form(
    request: Request,
    note_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Get edit form for a note (HTMX endpoint).

    Returns edit form HTML.
    """
    # Get note and validate
    note = uow.expenses.get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Only author can edit
    if note.author_id != user_id:
        raise HTTPException(status_code=403, detail="Only the author can edit this note")

    # Get expense to check status
    expense = uow.expenses.get_by_id(note.expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Cannot edit notes on settled expenses
    if expense.status == ExpenseStatus.SETTLED:
        return HTMLResponse(
            content="<div class='text-red-600 text-sm'>Cannot edit notes on settled expenses</div>",
            status_code=400,
        )

    return templates.TemplateResponse(
        request,
        "expenses/_expense_note_edit_form.html",
        {
            "note": note,
            "expense": expense,
        },
    )


@router.post("/expenses/notes/{note_id}/edit", response_class=HTMLResponse)
async def edit_expense_note(
    request: Request,
    note_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Edit an expense note (HTMX endpoint).

    Only the author can edit their own notes.
    Returns updated notes section HTML.
    """
    # Get form data
    form_data = await request.form()
    content = str(form_data.get("content", "")).strip()

    if not content:
        return HTMLResponse(
            content="<div class='text-red-600 text-sm'>Note cannot be empty</div>", status_code=400
        )

    # Get note and validate
    note = uow.expenses.get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Only author can edit
    if note.author_id != user_id:
        raise HTTPException(status_code=403, detail="Only the author can edit this note")

    # Get expense to check status
    expense = uow.expenses.get_by_id(note.expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Cannot edit notes on settled expenses
    if expense.status == ExpenseStatus.SETTLED:
        return HTMLResponse(
            content="<div class='text-red-600 text-sm'>Cannot edit notes on settled expenses</div>",
            status_code=400,
        )

    # Update note
    with uow:
        uow.expenses.update_note(note_id, content, actor_id=user_id)

    return _render_expense_notes_section(request, note.expense_id, user_id, uow)


@router.delete("/expenses/notes/{note_id}", response_class=HTMLResponse)
async def delete_expense_note(
    request: Request,
    note_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Delete an expense note (HTMX endpoint).

    Only the author can delete their own notes.
    Returns updated notes section HTML.
    """
    # Get note and validate
    note = uow.expenses.get_note_by_id(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Only author can delete
    if note.author_id != user_id:
        raise HTTPException(status_code=403, detail="Only the author can delete this note")

    # Get expense to check status
    expense = uow.expenses.get_by_id(note.expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Cannot delete notes on settled expenses
    if expense.status == ExpenseStatus.SETTLED:
        return HTMLResponse(
            content=(
                "<div class='text-red-600 text-sm'>Cannot delete notes on settled expenses</div>"
            ),
            status_code=400,
        )

    # Delete note
    with uow:
        uow.expenses.delete_note(note_id, actor_id=user_id)

    return _render_expense_notes_section(request, note.expense_id, user_id, uow)
