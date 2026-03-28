"""Shared helpers, constants, type aliases, and templates for expense routes."""

import contextlib
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.adapters.sqlalchemy.queries.dashboard_queries import get_group_members
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_current_user_id, get_uow
from app.domain.models import ExpenseStatus, UserPublic
from app.web.filters import get_currency_symbol
from app.web.templates import setup_templates

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
    """Get currency symbol for a given currency code.

    Delegates to the canonical implementation in app.web.filters.
    """
    return get_currency_symbol(default_currency)


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

    group_members = get_group_members(uow.session, group.id)
    all_user_ids = {member.user_id for member in group_members}
    all_user_ids.update(note.author_id for note in notes)
    users = uow.users.get_by_ids(list(all_user_ids))
    users_dict: dict[int, UserPublic] = {u.id: u for u in users}

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


class UpdateExpenseForm(BaseModel):
    """Form validation for expense updates."""

    amount: Decimal = Field(gt=0, le=Decimal("1000000.00"))
    description: str = Field(default="", max_length=200)
    date: date
    payer_id: int
    currency: str = Field(max_length=3)
    split_type: str = Field(default="even")
