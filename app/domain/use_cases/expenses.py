"""Expense domain use cases."""

from decimal import Decimal

from app.domain.errors import GroupNotFoundError
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
    from datetime import date as date_type

    # Validate group exists
    group = uow.groups.get_by_id(group_id)
    if group is None:
        raise GroupNotFoundError(f"Group {group_id} not found")

    # Default currency to group's configured default
    effective_currency = currency or group.default_currency

    # Default date to today
    effective_date = date or date_type.today()

    # Create expense with even split (Epic 2 only)
    expense = ExpensePublic(
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
