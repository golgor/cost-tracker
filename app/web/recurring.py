"""Route handlers for the recurring definitions registry and form."""

import json
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError  # noqa: F401

from app.adapters.sqlalchemy.queries.dashboard_queries import get_group_members
from app.adapters.sqlalchemy.queries.recurring_queries import (
    get_active_definitions,
    get_paused_definitions,
    get_registry_summary,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.errors import DomainError, InvalidShareError
from app.domain.models import (
    ExpensePublic,
    ExpenseStatus,
    RecurringFrequency,
    SplitType,
    UserPublic,
)
from app.domain.splits import (
    EvenSplitStrategy,
    ExactSplitStrategy,
    PercentageSplitStrategy,
    SharesSplitStrategy,
)
from app.domain.use_cases.recurring import (
    create_expense_from_definition,
    create_recurring_definition,
    delete_definition,
    pause_definition,
    reactivate_definition,
    update_recurring_definition,
)
from app.web.form_parsing import parse_amount, parse_date, parse_split_config
from app.web.templates import setup_templates

router = APIRouter(tags=["recurring"])
templates = setup_templates("app/templates")

CurrentUserId = Annotated[int, Depends(get_current_user_id)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]

_FREQUENCY_CHOICES = [
    ("MONTHLY", "Monthly"),
    ("QUARTERLY", "Quarterly"),
    ("SEMI_ANNUALLY", "Semi-Annually"),
    ("YEARLY", "Yearly"),
    ("EVERY_N_MONTHS", "Every N Months"),
]

_SPLIT_TYPE_CHOICES = [
    ("EVEN", "Even"),
    ("SHARES", "Shares"),
    ("PERCENTAGE", "Percentage"),
    ("EXACT", "Exact"),
]

_CATEGORY_CHOICES = [
    ("", "No category"),
    ("subscription", "Subscription"),
    ("insurance", "Insurance"),
    ("childcare", "Childcare"),
    ("utilities", "Utilities"),
    ("membership", "Membership"),
    ("other", "Other"),
]


def _build_form_options(form_data: dict[str, Any]) -> dict[str, Any]:
    """Build precomputed option lists with is_selected flags for the form template.

    Avoids string literal comparisons in templates (architecture rule).
    """
    split_type = form_data.get("split_type", "EVEN").upper()
    category = form_data.get("category", "")
    frequency = form_data.get("frequency", "MONTHLY")

    split_type_options = [
        {"value": v, "label": label, "is_selected": split_type == v}
        for v, label in _SPLIT_TYPE_CHOICES
    ]
    category_options = [
        {"value": v, "label": label, "is_selected": category == v} for v, label in _CATEGORY_CHOICES
    ]
    frequency_options = [
        {"value": v, "label": label, "is_selected": frequency == v}
        for v, label in _FREQUENCY_CHOICES
    ]

    return {
        "split_type_options": split_type_options,
        "category_options": category_options,
        "frequency_options": frequency_options,
        # Precomputed booleans for template visibility (no string comparisons in templates)
        "is_even_split": split_type == "EVEN",
        "is_every_n_months": frequency == "EVERY_N_MONTHS",
        "has_category": bool(category),
    }


def _build_users_dict(
    members: list,
    uow: UnitOfWork,
) -> dict[int, UserPublic]:
    member_ids = [member.user_id for member in members]
    users = uow.users.get_by_ids(member_ids)
    return {u.id: u for u in users}


@router.get("/recurring", response_class=HTMLResponse)
async def registry_index(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render the recurring definitions registry (Active tab by default)."""
    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No household group found",
            )
        user = uow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        definitions = get_active_definitions(uow.session, group.id)
        summary = get_registry_summary(uow.session, group.id)

    return templates.TemplateResponse(
        request,
        "recurring/index.html",
        {
            "user": user,
            "group": group,
            "definitions": definitions,
            "summary": summary,
            "active_tab": "active",
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.get("/recurring/new", response_class=HTMLResponse)
async def new_recurring_form(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render the create recurring definition form."""
    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(status_code=404, detail="No household group found")
        user = uow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        members = get_group_members(uow.session, group.id)
        users_dict = _build_users_dict(members, uow)

    form_data: dict[str, Any] = {
        "name": "",
        "amount": "",
        "frequency": "MONTHLY",
        "interval_months": "",
        "next_due_date": date.today().isoformat(),
        "payer_id": user_id,
        "split_type": "EVEN",
        "split_config": "",
        "category": "",
        "auto_generate": False,
    }
    opts = _build_form_options(form_data)

    return templates.TemplateResponse(
        request,
        "recurring/form.html",
        {
            "user": user,
            "is_edit": False,
            "definition": None,
            "form_data": form_data,
            "errors": {},
            "members": members,
            "users": users_dict,
            **opts,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/recurring", response_class=HTMLResponse)
async def create_recurring(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    name: Annotated[str, Form()] = "",
    amount_str: Annotated[str, Form(alias="amount")] = "",
    frequency: Annotated[str, Form()] = "MONTHLY",
    interval_months_str: Annotated[str, Form(alias="interval_months")] = "",
    next_due_date_str: Annotated[str, Form(alias="next_due_date")] = "",
    payer_id_str: Annotated[str, Form(alias="payer_id")] = "",
    split_type: Annotated[str, Form()] = "EVEN",
    split_config_json: Annotated[str, Form(alias="split_config")] = "",
    category: Annotated[str, Form()] = "",
    auto_generate_str: Annotated[str, Form(alias="auto_generate")] = "",
):
    """Handle create recurring definition form submission."""

    try:
        payer_id = int(payer_id_str)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid payer_id") from exc

    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(status_code=404, detail="No household group found")

        user = uow.users.get_by_id(user_id)
        members = get_group_members(uow.session, group.id)
        users_dict = _build_users_dict(members, uow)

        form_data: dict[str, Any] = {
            "name": name,
            "amount": amount_str,
            "frequency": frequency,
            "interval_months": interval_months_str,
            "next_due_date": next_due_date_str,
            "payer_id": payer_id,
            "split_type": split_type,
            "split_config": split_config_json,
            "category": category,
            "auto_generate": auto_generate_str == "on",
        }

        errors, parsed = _parse_form(form_data)

        if not errors and parsed["split_enum"] != SplitType.EVEN:
            member_ids = [m.user_id for m in members]
            try:
                _validate_split_with_strategies(
                    split_type=parsed["split_enum"],
                    split_config=parsed["split_config"],
                    amount=parsed["amount"],
                    payer_id=payer_id,
                    member_ids=member_ids,
                )
            except (InvalidShareError, ValueError) as exc:
                errors["split_type"] = str(exc)

        if not errors:
            try:
                create_recurring_definition(
                    uow,
                    group_id=group.id,
                    name=name,
                    amount=parsed["amount"],
                    frequency=parsed["frequency"],
                    next_due_date=parsed["next_due_date"],
                    payer_id=payer_id,
                    split_type=parsed["split_enum"],
                    split_config=parsed["split_config"],
                    interval_months=parsed["interval_months"],
                    category=category or None,
                    auto_generate=auto_generate_str == "on",
                )
            except DomainError as exc:
                errors["__all__"] = str(exc)

        if errors:
            opts = _build_form_options(form_data)
            return templates.TemplateResponse(
                request,
                "recurring/form.html",
                {
                    "user": user,
                    "is_edit": False,
                    "definition": None,
                    "form_data": form_data,
                    "errors": errors,
                    "members": members,
                    "users": users_dict,
                    **opts,
                    "csrf_token": getattr(request.state, "csrf_token", ""),
                },
                status_code=422,
            )

    return RedirectResponse(url="/recurring", status_code=303)


@router.get("/recurring/tab/{tab}", response_class=HTMLResponse)
async def registry_tab(
    request: Request,
    tab: str,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """HTMX partial: switch between Active and Paused tabs."""
    if tab not in ("active", "paused"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tab")

    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No household group found",
            )

        if tab == "active":
            definitions = get_active_definitions(uow.session, group.id)
        else:
            definitions = get_paused_definitions(uow.session, group.id)

        summary = get_registry_summary(uow.session, group.id)

    return templates.TemplateResponse(
        request,
        "recurring/_definition_list.html",
        {
            "definitions": definitions,
            "summary": summary,
            "active_tab": tab,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.get("/recurring/{definition_id}/edit", response_class=HTMLResponse)
async def edit_recurring_form(
    request: Request,
    definition_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render the edit recurring definition form."""
    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(status_code=404, detail="No household group found")

        user = uow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        definition = uow.recurring.get_by_id(definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Recurring definition not found")

        members = get_group_members(uow.session, group.id)
        users_dict = _build_users_dict(members, uow)

    form_data: dict[str, Any] = {
        "name": definition.name,
        "amount": str(definition.amount),
        "frequency": definition.frequency.value,
        "interval_months": str(definition.interval_months) if definition.interval_months else "",
        "next_due_date": definition.next_due_date.isoformat(),
        "payer_id": definition.payer_id,
        "split_type": definition.split_type.value,
        "split_config": json.dumps({str(k): str(v) for k, v in definition.split_config.items()})
        if definition.split_config
        else "",
        "category": definition.category or "",
        "auto_generate": definition.auto_generate,
    }
    opts = _build_form_options(form_data)

    return templates.TemplateResponse(
        request,
        "recurring/form.html",
        {
            "user": user,
            "is_edit": True,
            "definition": definition,
            "form_data": form_data,
            "errors": {},
            "members": members,
            "users": users_dict,
            **opts,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.post("/recurring/{definition_id}", response_class=HTMLResponse)
async def update_recurring(
    request: Request,
    definition_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
    name: Annotated[str, Form()] = "",
    amount_str: Annotated[str, Form(alias="amount")] = "",
    frequency: Annotated[str, Form()] = "MONTHLY",
    interval_months_str: Annotated[str, Form(alias="interval_months")] = "",
    next_due_date_str: Annotated[str, Form(alias="next_due_date")] = "",
    payer_id_str: Annotated[str, Form(alias="payer_id")] = "",
    split_type: Annotated[str, Form()] = "EVEN",
    split_config_json: Annotated[str, Form(alias="split_config")] = "",
    category: Annotated[str, Form()] = "",
    auto_generate_str: Annotated[str, Form(alias="auto_generate")] = "",
):
    """Handle update recurring definition form submission."""

    try:
        payer_id = int(payer_id_str)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Invalid payer_id") from exc

    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(status_code=404, detail="No household group found")

        user = uow.users.get_by_id(user_id)
        definition = uow.recurring.get_by_id(definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Recurring definition not found")

        members = get_group_members(uow.session, group.id)
        users_dict = _build_users_dict(members, uow)

        form_data: dict[str, Any] = {
            "name": name,
            "amount": amount_str,
            "frequency": frequency,
            "interval_months": interval_months_str,
            "next_due_date": next_due_date_str,
            "payer_id": payer_id,
            "split_type": split_type,
            "split_config": split_config_json,
            "category": category,
            "auto_generate": auto_generate_str == "on",
        }

        errors, parsed = _parse_form(form_data)

        if not errors and parsed["split_enum"] != SplitType.EVEN:
            member_ids = [m.user_id for m in members]
            try:
                _validate_split_with_strategies(
                    split_type=parsed["split_enum"],
                    split_config=parsed["split_config"],
                    amount=parsed["amount"],
                    payer_id=payer_id,
                    member_ids=member_ids,
                )
            except (InvalidShareError, ValueError) as exc:
                errors["split_type"] = str(exc)

        if not errors:
            try:
                update_recurring_definition(
                    uow,
                    definition_id=definition_id,
                    name=name,
                    amount=parsed["amount"],
                    frequency=parsed["frequency"],
                    next_due_date=parsed["next_due_date"],
                    payer_id=payer_id,
                    split_type=parsed["split_enum"],
                    split_config=parsed["split_config"],
                    interval_months=parsed["interval_months"],
                    category=category or None,
                    auto_generate=auto_generate_str == "on",
                )
            except DomainError as exc:
                errors["__all__"] = str(exc)

        if errors:
            opts = _build_form_options(form_data)
            return templates.TemplateResponse(
                request,
                "recurring/form.html",
                {
                    "user": user,
                    "is_edit": True,
                    "definition": definition,
                    "form_data": form_data,
                    "errors": errors,
                    "members": members,
                    "users": users_dict,
                    **opts,
                    "csrf_token": getattr(request.state, "csrf_token", ""),
                },
                status_code=422,
            )

    return RedirectResponse(url="/recurring", status_code=303)


@router.patch("/recurring/{definition_id}/toggle-active", response_class=HTMLResponse)
async def toggle_active(
    request: Request,
    definition_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """HTMX: toggle pause/resume on a recurring definition. Returns updated card."""
    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(status_code=404, detail="No household group found")

        definition = uow.recurring.get_by_id(definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Recurring definition not found")

        if definition.is_active:
            pause_definition(uow, definition_id)
        else:
            reactivate_definition(uow, definition_id)

        # Re-fetch updated definition for card render
        from app.adapters.sqlalchemy.orm_models import RecurringDefinitionRow
        from app.adapters.sqlalchemy.queries.recurring_queries import (
            _build_definition_view,
            _get_payer_map,
        )

        row = uow.session.get(RecurringDefinitionRow, definition_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Recurring definition not found")
        payer_map = _get_payer_map(uow.session, {row.payer_id})
        defn = _build_definition_view(row, payer_map)

    return templates.TemplateResponse(
        request,
        "recurring/_definition_card.html",
        {
            "defn": defn,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


@router.delete("/recurring/{definition_id}", response_class=HTMLResponse)
async def delete_recurring(
    request: Request,
    definition_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """HTMX: soft-delete a recurring definition. Returns empty 200 (removes card from DOM)."""
    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(status_code=404, detail="No household group found")

        delete_definition(uow, definition_id)

    return HTMLResponse(content="", status_code=200)


@router.post("/recurring/{definition_id}/create-expense", response_class=HTMLResponse)
async def create_expense_for_definition(
    request: Request,
    definition_id: int,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """HTMX: create an expense for the current billing period and advance due date.

    Returns the updated card so HTMX can swap it in place.
    """
    with uow:
        group = uow.groups.get_by_user_id(user_id)
        if group is None:
            raise HTTPException(status_code=404, detail="No household group found")

        definition = uow.recurring.get_by_id(definition_id)
        if definition is None:
            raise HTTPException(status_code=404, detail="Recurring definition not found")
        create_expense_from_definition(uow, definition)

        from app.adapters.sqlalchemy.orm_models import RecurringDefinitionRow
        from app.adapters.sqlalchemy.queries.recurring_queries import (
            _build_definition_view,
            _get_payer_map,
        )

        row = uow.session.get(RecurringDefinitionRow, definition_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Recurring definition not found")
        payer_map = _get_payer_map(uow.session, {row.payer_id})
        defn = _build_definition_view(row, payer_map)

    return templates.TemplateResponse(
        request,
        "recurring/_definition_card.html",
        {
            "defn": defn,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )


def _validate_split_with_strategies(
    split_type: SplitType,
    split_config: dict[int, str] | None,
    amount: Decimal,
    payer_id: int,
    member_ids: list[int],
) -> None:
    """Validate split_config using the real domain strategies.

    Raises InvalidShareError or ValueError with a user-friendly message on failure.
    This is the single source of truth for split validation — no ad-hoc duplication.
    """
    if split_type == SplitType.EVEN:
        EvenSplitStrategy().calculate_shares(_mock_expense(amount, payer_id), member_ids)
        return

    if not split_config:
        raise InvalidShareError("Split configuration is required for non-even splits")

    # Convert stored strings back to Decimal for strategy validation
    config_decimal: dict[int, Decimal] = {k: Decimal(v) for k, v in split_config.items()}
    mock = _mock_expense(amount, payer_id)

    if split_type == SplitType.SHARES:
        SharesSplitStrategy().calculate_shares(mock, member_ids, config_decimal)
    elif split_type == SplitType.PERCENTAGE:
        PercentageSplitStrategy().calculate_shares(mock, member_ids, config_decimal)
    elif split_type == SplitType.EXACT:
        ExactSplitStrategy().calculate_shares(mock, member_ids, config_decimal)


def _mock_expense(amount: Decimal, payer_id: int) -> ExpensePublic:
    """Create a minimal mock expense for strategy validation."""
    return ExpensePublic.model_construct(
        id=0,
        group_id=0,
        amount=amount,
        description="",
        date=date.today(),
        creator_id=payer_id,
        payer_id=payer_id,
        currency="EUR",
        split_type=SplitType.EVEN,
        status=ExpenseStatus.PENDING,
        created_at=None,  # type: ignore[arg-type]
        updated_at=None,  # type: ignore[arg-type]
    )


def _parse_form(
    form_data: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    """Parse and validate raw form data. Returns (errors, parsed_values)."""
    errors: dict[str, str] = {}
    parsed: dict[str, Any] = {}

    # Validate name
    name = str(form_data.get("name", "")).strip()
    if not name:
        errors["name"] = "Name is required"

    # Parse amount
    amount_str = form_data.get("amount", "")
    amount = parse_amount(str(amount_str))
    if amount is None:
        errors["amount"] = "Invalid amount format"
        parsed["amount"] = Decimal("0")
    elif amount <= 0:
        errors["amount"] = "Amount must be greater than zero"
        parsed["amount"] = amount
    else:
        parsed["amount"] = amount

    # Parse next_due_date
    next_due_date_str = form_data.get("next_due_date", "")
    parsed_date = parse_date(str(next_due_date_str))
    if parsed_date is None:
        errors["next_due_date"] = "Invalid date format"
        parsed["next_due_date"] = date.today()
    else:
        parsed["next_due_date"] = parsed_date

    # Parse interval_months
    interval_str = str(form_data.get("interval_months", "")).strip()
    parsed["interval_months"] = None
    if interval_str:
        try:
            val = int(interval_str)
            if val < 1:
                errors["interval_months"] = "Interval must be at least 1 month"
            else:
                parsed["interval_months"] = val
        except ValueError:
            errors["interval_months"] = "Interval must be a whole number"

    # Parse frequency enum
    try:
        parsed["frequency"] = RecurringFrequency(form_data.get("frequency", ""))
    except ValueError:
        errors["frequency"] = "Invalid frequency"
        parsed["frequency"] = RecurringFrequency.MONTHLY

    # Parse split_type enum
    try:
        parsed["split_enum"] = SplitType(str(form_data.get("split_type", "EVEN")).upper())
    except ValueError:
        errors["split_type"] = "Invalid split type"
        parsed["split_enum"] = SplitType.EVEN

    # Parse split_config — store as {int: str} (Decimal is not JSON-serializable)
    # Business rule validation (sum, positive values) happens in the route handler
    # via _validate_split_with_strategies, which uses the domain strategies directly.
    parsed["split_config"] = None
    split_config_json = form_data.get("split_config", "")
    if parsed["split_enum"] != SplitType.EVEN and split_config_json:
        config = parse_split_config(str(split_config_json))
        if config is None:
            errors["split_type"] = "Invalid split configuration"
        else:
            parsed["split_config"] = {k: str(v) for k, v in config.items()}

    # Validate EVERY_N_MONTHS constraint
    if (
        parsed["frequency"] == RecurringFrequency.EVERY_N_MONTHS
        and "frequency" not in errors
        and parsed["interval_months"] is None
        and "interval_months" not in errors
    ):
        errors["interval_months"] = "Interval is required for 'Every N Months'"

    return errors, parsed
