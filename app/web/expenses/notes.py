"""Expense notes CRUD endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.domain.models import ExpenseNotePublic, ExpenseStatus
from app.web.expenses._shared import (
    CurrentUserId,
    UowDep,
    _render_expense_notes_section,
    templates,
)

router = APIRouter(tags=["expenses"])


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
    content: Annotated[str, Form()] = "",
):
    """Add a note to an expense (HTMX endpoint).

    Returns updated notes section HTML.
    """
    content = content.strip()

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
    with uow:
        note = ExpenseNotePublic(
            id=0,
            expense_id=expense_id,
            author_id=user_id,
            content=content,
            created_at=datetime.now(),  # Placeholder, will be set by database
            updated_at=datetime.now(),  # Placeholder, will be set by database
        )
        uow.expenses.save_note(note)

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
    content: Annotated[str, Form()] = "",
):
    """Edit an expense note (HTMX endpoint).

    Only the author can edit their own notes.
    Returns updated notes section HTML.
    """
    content = content.strip()

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
        uow.expenses.update_note(note_id, content)

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
        uow.expenses.delete_note(note_id)

    return _render_expense_notes_section(request, note.expense_id, user_id, uow)
