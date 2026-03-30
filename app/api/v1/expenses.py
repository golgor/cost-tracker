"""Expense CRUD endpoints for the external API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.dependencies import get_uow
from app.domain.models import ExpensePublic

router = APIRouter(prefix="/expenses", tags=["expenses"])

UowDep = Annotated[UnitOfWork, Depends(get_uow)]


@router.get("", response_model=list[ExpensePublic])
def list_expenses(uow: UowDep) -> list[ExpensePublic]:
    """List all expenses, ordered by date descending."""
    with uow:
        return uow.expenses.list_all()


@router.get("/{expense_id}", response_model=ExpensePublic)
def get_expense(expense_id: int, uow: UowDep) -> ExpensePublic:
    """Retrieve a single expense by ID."""
    with uow:
        expense = uow.expenses.get_by_id(expense_id)
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Expense {expense_id} not found"
        )
    return expense
