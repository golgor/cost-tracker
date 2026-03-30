"""Expense CRUD endpoints for the external API."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.api.v1.schemas import ExpenseCreateRequest, ExpenseUpdateRequest
from app.dependencies import get_uow
from app.domain.errors import ExpenseNotFoundError
from app.domain.models import ExpensePublic
from app.domain.use_cases.expenses import create_expense, update_expense

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
        raise ExpenseNotFoundError(expense_id)
    return expense


@router.post("", response_model=ExpensePublic, status_code=status.HTTP_201_CREATED)
def create_expense_endpoint(body: ExpenseCreateRequest, uow: UowDep) -> ExpensePublic:
    """Create a new expense with automatic split calculation."""
    with uow:
        return create_expense(
            uow=uow,
            amount=body.amount,
            description=body.description,
            creator_id=body.creator_id,
            payer_id=body.payer_id,
            member_ids=body.member_ids,
            currency=body.currency,
            date=body.date,
            split_type=body.split_type,
            split_config=body.split_config,
        )


@router.put("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def update_expense_endpoint(expense_id: int, body: ExpenseUpdateRequest, uow: UowDep) -> None:
    """Update an existing expense. Settled expenses cannot be modified."""
    with uow:
        update_expense(
            uow=uow,
            expense_id=expense_id,
            amount=body.amount,
            description=body.description,
            date=body.date,
            payer_id=body.payer_id,
            currency=body.currency,
            split_type=body.split_type,
            split_config=body.split_config,
            member_ids=body.member_ids,
        )
