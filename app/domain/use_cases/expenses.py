"""Expense domain use cases."""

from datetime import date as date_type
from decimal import Decimal

from app.domain.errors import (
    CannotEditSettledExpenseError,
    DomainError,
    GroupNotFoundError,
    InvalidShareError,
    RecurringExpenseDescriptionError,
)
from app.domain.models import ExpensePublic, ExpenseSplitPublic, ExpenseStatus, SplitType
from app.domain.ports import UnitOfWorkPort
from app.domain.splits import (
    EvenSplitStrategy,
    ExactSplitStrategy,
    PercentageSplitStrategy,
    SharesSplitStrategy,
)


def create_expense(
    uow: UnitOfWorkPort,
    group_id: int,
    amount: Decimal,
    description: str,
    creator_id: int,
    payer_id: int,
    member_ids: list[int],
    currency: str | None = None,
    date=None,
    split_type: str = "EVEN",
    split_config: dict[int, Decimal] | None = None,
) -> ExpensePublic:
    """Create a shared expense.

    Args:
        uow: Unit of work for transaction management
        group_id: ID of the group/household this expense belongs to
        amount: Decimal amount (must be > 0)
        description: Description of the expense (e.g., "Spar", "Netflix")
        creator_id: User ID who entered the expense
        payer_id: User ID who actually paid the bill
        member_ids: List of user IDs who are members of the group (for split calculation)
        currency: Currency code (defaults to group's configured currency)
        date: Expense date (defaults to today)
        split_type: How to split the expense (EVEN, SHARES, PERCENTAGE, EXACT)
        split_config: Configuration for non-even splits:
            - SHARES: dict[user_id, share_count]
            - PERCENTAGE: dict[user_id, percentage] (e.g., Decimal("60") for 60%)
            - EXACT: dict[user_id, exact_amount]

    Returns:
        The persisted ExpensePublic with generated ID.

    Raises:
        GroupNotFoundError: If the group doesn't exist
        InvalidShareError: If split configuration is invalid
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

    # Normalize split_type to enum
    split_type_enum = SplitType(split_type.upper())

    # Calculate expense splits
    expense_model = ExpensePublic.model_construct(
        id=0,  # Placeholder ID
        group_id=group_id,
        amount=amount,
        description=description,
        date=effective_date,
        creator_id=creator_id,
        payer_id=payer_id,
        currency=effective_currency,
        split_type=split_type_enum,
        status=ExpenseStatus.PENDING,
    )

    # Calculate splits based on type
    splits = _calculate_splits(
        expense=expense_model,
        member_ids=member_ids,
        split_type=split_type_enum,
        split_config=split_config,
    )

    # Create expense with computed split_type
    expense = ExpensePublic.model_construct(
        group_id=group_id,
        amount=amount,
        description=description,
        date=effective_date,
        creator_id=creator_id,
        payer_id=payer_id,
        currency=effective_currency,
        split_type=split_type_enum,
        status=ExpenseStatus.PENDING,
    )

    # Persist expense
    saved_expense = uow.expenses.save(expense, actor_id=creator_id)

    # Persist splits
    split_publics = [
        ExpenseSplitPublic.model_construct(
            id=0,  # Placeholder ID
            expense_id=saved_expense.id,
            user_id=user_id,
            amount=split_amount,
            share_value=share_value,
        )
        for user_id, split_amount, share_value in splits
    ]
    uow.expenses.save_splits(saved_expense.id, split_publics, actor_id=creator_id)

    return saved_expense


def _calculate_splits(
    expense: ExpensePublic,
    member_ids: list[int],
    split_type: SplitType,
    split_config: dict[int, Decimal] | None,
) -> list[tuple[int, Decimal, Decimal | None]]:
    """Calculate split amounts for each member.

    Returns list of (user_id, amount, share_value) tuples.
    share_value is None for EVEN/EXACT, populated for SHARES/PERCENTAGE.
    """
    if split_type == SplitType.EVEN:
        strategy = EvenSplitStrategy()
        shares = strategy.calculate_shares(expense, member_ids)
        return [(user_id, share.amount, None) for user_id, share in shares.items()]

    if split_type == SplitType.SHARES:
        if not split_config:
            raise InvalidShareError("Shares split requires split_config with share counts")
        strategy = SharesSplitStrategy()
        shares = strategy.calculate_shares(expense, member_ids, split_config)
        return [
            (user_id, share.amount, split_config.get(user_id)) for user_id, share in shares.items()
        ]

    if split_type == SplitType.PERCENTAGE:
        if not split_config:
            raise InvalidShareError("Percentage split requires split_config with percentages")
        strategy = PercentageSplitStrategy()
        shares = strategy.calculate_shares(expense, member_ids, split_config)
        return [
            (user_id, share.amount, split_config.get(user_id)) for user_id, share in shares.items()
        ]

    if split_type == SplitType.EXACT:
        if not split_config:
            raise InvalidShareError("Exact split requires split_config with exact amounts")
        strategy = ExactSplitStrategy()
        shares = strategy.calculate_shares(expense, member_ids, split_config)
        return [(user_id, share.amount, None) for user_id, share in shares.items()]

    raise DomainError(f"Unknown split type: {split_type}")


def update_expense(
    uow: UnitOfWorkPort,
    expense_id: int,
    actor_id: int,
    amount: Decimal | None = None,
    description: str | None = None,
    date: date_type | None = None,
    payer_id: int | None = None,
    currency: str | None = None,
    split_type: str | None = None,
    split_config: dict[int, Decimal] | None = None,
    member_ids: list[int] | None = None,
) -> None:
    """Update an existing expense.

    Validates:
    - Expense must not be settled (immutability check)
    - Amount must be positive
    - Date cannot be in the future

    Audit logging: Records all changed fields with previous values.
    Recalculates splits when amount or split type changes.

    Args:
        uow: Unit of work for transaction management
        expense_id: ID of expense to update
        actor_id: User ID performing the update
        amount: New amount (optional)
        description: New description (optional)
        date: New date (optional)
        payer_id: New payer ID (optional)
        currency: New currency (optional)
        split_type: New split type (optional, e.g. "even", "shares")
        split_config: Split configuration for non-even splits (optional)
        member_ids: Group member IDs for split calculation (required if split_type changes)

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

    # Description is locked for recurring expenses
    if description is not None and expense.recurring_definition_id is not None:
        raise RecurringExpenseDescriptionError(
            "Cannot change the description of a recurring expense"
        )

    # Validation
    if amount is not None and amount <= 0:
        raise DomainError("Amount must be greater than zero")

    if date and date > date_type.today():
        raise DomainError("Expense date cannot be in the future")

    # Parse split_type enum if provided
    split_type_enum: SplitType | None = None
    if split_type is not None:
        try:
            split_type_enum = SplitType(split_type.upper())
        except ValueError as err:
            raise DomainError(f"Invalid split type: {split_type}") from err

    # Update expense fields (adapter handles change tracking and audit)
    uow.expenses.update(
        expense_id=expense_id,
        amount=amount,
        description=description,
        date=date,
        payer_id=payer_id,
        currency=currency,
        actor_id=actor_id,
    )

    # Update split_type on the expense row if changed
    if split_type_enum is not None and split_type_enum != expense.split_type:
        uow.expenses.update(
            expense_id=expense_id,
            split_type=split_type_enum,
            actor_id=actor_id,
        )

    # Recalculate splits when amount or split type changes
    amount_changed = amount is not None and amount != expense.amount
    split_type_changed = split_type_enum is not None and split_type_enum != expense.split_type
    if amount_changed or split_type_changed or split_config is not None:
        updated_expense = uow.expenses.get_by_id(expense_id)
        if updated_expense is None:
            raise DomainError(f"Expense {expense_id} not found after update")

        # Determine member IDs: use provided list, or fall back to existing splits
        effective_member_ids = member_ids
        if not effective_member_ids:
            current_splits = uow.expenses.get_splits(expense_id)
            effective_member_ids = [s.user_id for s in current_splits]

        if effective_member_ids:
            # Use provided split_config, or rebuild from existing share_values
            effective_config = split_config
            if effective_config is None and not split_type_changed:
                current_splits = uow.expenses.get_splits(expense_id)
                if updated_expense.split_type in (
                    SplitType.SHARES,
                    SplitType.PERCENTAGE,
                    SplitType.EXACT,
                ):
                    effective_config = {
                        s.user_id: s.share_value
                        for s in current_splits
                        if s.share_value is not None
                    }

            new_splits = _calculate_splits(
                expense=updated_expense,
                member_ids=effective_member_ids,
                split_type=updated_expense.split_type,
                split_config=effective_config,
            )

            split_publics = [
                ExpenseSplitPublic.model_construct(
                    id=0,
                    expense_id=expense_id,
                    user_id=uid,
                    amount=split_amount,
                    share_value=share_value,
                )
                for uid, split_amount, share_value in new_splits
            ]
            uow.expenses.save_splits(expense_id, split_publics, actor_id=actor_id)


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
