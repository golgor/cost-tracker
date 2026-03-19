"""Expense domain use cases."""

from datetime import date as date_type
from decimal import Decimal

from app.domain.errors import CannotEditSettledExpenseError, DomainError, GroupNotFoundError
from app.domain.models import ExpensePublic, ExpenseStatus, SplitType
from app.domain.ports import UnitOfWorkPort


def create_expense(
    uow: UnitOfWorkPort,
    group_id: int,
    amount: Decimal,
    description: str,
    creator_id: int,
    payer_id: int,
    currency: str | None = None,
    date=None,
) -> ExpensePublic:
    """Create a shared expense.

    Args:
        uow: Unit of work for transaction management
        group_id: ID of the group/household this expense belongs to
        amount: Decimal amount (must be > 0)
        description: Description of the expense (e.g., "Spar", "Netflix")
        creator_id: User ID who entered the expense
        payer_id: User ID who actually paid the bill
        currency: Currency code (defaults to group's configured currency)
        date: Expense date (defaults to today)

    Returns:
        The persisted ExpensePublic with generated ID.

    Raises:
        GroupNotFoundError: If the group doesn't exist
        ValidationError: If amount or other fields fail validation

    Transaction must be committed by caller using `with uow:`.
    """
    # Validate group exists
    group = uow.groups.get_by_id(group_id)
    if group is None:
        raise GroupNotFoundError(f"Group {group_id} not found")

    # Default currency to group's configured default
    effective_currency = currency or group.default_currency

    # Default date to today
    effective_date = date or date_type.today()

    # Create expense with even split (Epic 2 only)
    # Use model_construct to bypass validation since id/created_at/updated_at are DB-generated
    expense = ExpensePublic.model_construct(
        group_id=group_id,
        amount=amount,
        description=description,
        date=effective_date,
        creator_id=creator_id,
        payer_id=payer_id,
        currency=effective_currency,
        split_type=SplitType.EVEN,
        status=ExpenseStatus.PENDING,
    )

    # Persist with audit logging
    saved_expense = uow.expenses.save(expense, actor_id=creator_id)

    return saved_expense


def update_expense(
    uow: UnitOfWorkPort,
    expense_id: int,
    actor_id: int,
    amount: Decimal | None = None,
    description: str | None = None,
    date: date_type | None = None,
    payer_id: int | None = None,
    currency: str | None = None,
) -> None:
    """Update an existing expense.

    Validates:
    - Expense must not be settled (immutability check)
    - Amount must be positive
    - Date cannot be in the future

    Audit logging: Records all changed fields with previous values.

    Args:
        uow: Unit of work for transaction management
        expense_id: ID of expense to update
        actor_id: User ID performing the update
        amount: New amount (optional)
        description: New description (optional)
        date: New date (optional)
        payer_id: New payer ID (optional)
        currency: New currency (optional)

    Raises:
        CannotEditSettledExpenseError: If expense is settled
        DomainError: If validation fails
    """
    # Get existing expense
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise DomainError(f"Expense {expense_id} not found")

    # Immutability check: cannot edit settled expenses
    if expense.status == ExpenseStatus.SETTLED:
        raise CannotEditSettledExpenseError(expense_id)

    # Validation
    if amount is not None and amount <= 0:
        raise DomainError("Amount must be greater than zero")

    if date and date > date_type.today():
        raise DomainError("Expense date cannot be in the future")

    # Update fields (adapter handles change tracking and audit)
    uow.expenses.update(
        expense_id=expense_id,
        amount=amount,
        description=description,
        date=date,
        payer_id=payer_id,
        currency=currency,
        actor_id=actor_id,
    )


def delete_expense(
    uow: UnitOfWorkPort,
    expense_id: int,
    actor_id: int,
) -> None:
    """Delete an expense (only if unsettled).

    Validates:
    - Expense must exist
    - Expense must not be settled (immutability check)

    Audit logging: Records deletion with pre-delete snapshot of all fields.

    Args:
        uow: Unit of work for transaction management
        expense_id: ID of expense to delete
        actor_id: User ID performing the deletion

    Raises:
        DomainError: If expense not found
        CannotEditSettledExpenseError: If expense is settled (immutable)
    """
    # Get existing expense
    expense = uow.expenses.get_by_id(expense_id)
    if not expense:
        raise DomainError(f"Expense {expense_id} not found")

    # Immutability check: cannot delete settled expenses
    if expense.status == ExpenseStatus.SETTLED:
        raise CannotEditSettledExpenseError(expense_id)

    # Delete (adapter handles audit logging with snapshot)
    uow.expenses.delete(expense_id=expense_id, actor_id=actor_id)

