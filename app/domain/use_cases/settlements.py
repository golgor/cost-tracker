"""Settlement domain use cases."""

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.balance import (
    MemberBalance,
    SettlementTransaction,
    calculate_balances_from_splits,
    minimize_transactions,
)
from app.domain.errors import EmptySettlementError, SettlementError, StaleExpenseError
from app.domain.models import (
    ExpensePublic,
    ExpenseStatus,
    SettlementBase,
    SettlementPublic,
    SettlementTransactionBase,
)
from app.domain.ports import UnitOfWorkPort


def _load_splits_and_calculate(
    uow: UnitOfWorkPort,
    expenses: list[ExpensePublic],
    member_ids: list[int],
) -> dict[int, MemberBalance]:
    """Load persisted splits and calculate balances."""
    splits_by_expense: dict[int, list[tuple[int, Decimal]]] = {}
    for expense in expenses:
        raw_splits = uow.expenses.get_splits(expense.id)
        splits_by_expense[expense.id] = [(s.user_id, s.amount) for s in raw_splits]

    return calculate_balances_from_splits(expenses, splits_by_expense, member_ids)


def format_transfer_message(
    transactions: list[SettlementTransaction],
    display_names: dict[int, str],
) -> str:
    """Generate human-readable transfer message from transactions.

    Args:
        transactions: List of settlement transactions from minimize_transactions()
        display_names: Mapping of user IDs to display names

    Returns:
        Human-readable message describing the transfers
    """
    if not transactions:
        return "No payment needed"
    if len(transactions) == 1:
        tx = transactions[0]
        from_name = display_names.get(tx.from_user_id, f"User {tx.from_user_id}")
        to_name = display_names.get(tx.to_user_id, f"User {tx.to_user_id}")
        return f"{from_name} pays {to_name}"
    return f"{len(transactions)} payments required"


def generate_reference_id(uow: UnitOfWorkPort) -> str:
    """Generate unique human-readable reference ID.

    Format: "March 2025" or "March 2025 (2)" if duplicate exists.
    Uses unbounded query to ensure uniqueness across all settlements.
    """
    now = datetime.now(UTC)
    base = now.strftime("%B %Y")

    if not uow.settlements.reference_exists(base):
        return base

    counter = 2
    max_attempts = 100
    while uow.settlements.reference_exists(f"{base} ({counter})"):
        counter += 1
        if counter > max_attempts:
            raise SettlementError(
                f"Could not generate unique reference ID after {max_attempts} attempts"
            )

    return f"{base} ({counter})"


def preview_settlement(
    uow: UnitOfWorkPort,
    expense_ids: list[int],
    member_ids: list[int],
) -> tuple[list[SettlementTransaction], dict[int, MemberBalance]]:
    """Calculate settlement preview without persisting anything.

    Loads and validates expenses, computes balances, and minimizes transactions.

    Args:
        uow: Unit of work for reading expenses
        expense_ids: IDs of expenses to include in the preview
        member_ids: All member user IDs in the group

    Returns:
        Tuple of (transactions, balances) for display

    Raises:
        SettlementError: If an expense doesn't exist
        StaleExpenseError: If an expense is already settled
    """
    expense_ids = list(dict.fromkeys(expense_ids))  # deduplicate, preserve order
    expenses: list[ExpensePublic] = []
    for expense_id in expense_ids:
        expense = uow.expenses.get_by_id(expense_id)
        if expense is None:
            raise SettlementError(f"Expense {expense_id} no longer exists")
        if expense.status == ExpenseStatus.SETTLED:
            raise StaleExpenseError(expense_id)
        expenses.append(expense)

    balances = _load_splits_and_calculate(uow, expenses, member_ids)
    transactions = minimize_transactions(balances)
    return transactions, balances


def confirm_settlement(
    uow: UnitOfWorkPort,
    *,
    expense_ids: list[int],
    settled_by_id: int,
    member_ids: list[int],
    reference_id: str | None = None,
) -> SettlementPublic:
    """Confirm a settlement and mark expenses as settled.

    Args:
        uow: Unit of work for transaction boundary
        expense_ids: IDs of expenses to include
        settled_by_id: User confirming the settlement
        member_ids: All user IDs in the household
        reference_id: Optional custom reference (auto-generated if None)

    Returns:
        The created settlement

    Raises:
        EmptySettlementError: If expense_ids is empty
        StaleExpenseError: If an expense is already settled
    """
    if not expense_ids:
        raise EmptySettlementError()

    expense_ids = list(dict.fromkeys(expense_ids))  # deduplicate, preserve order
    expenses: list[ExpensePublic] = []
    for expense_id in expense_ids:
        expense = uow.expenses.get_by_id(expense_id)
        if expense is None:
            raise SettlementError(f"Expense {expense_id} no longer exists")
        if expense.status == ExpenseStatus.SETTLED:
            raise StaleExpenseError(expense_id)
        expenses.append(expense)

    balances = _load_splits_and_calculate(uow, expenses, member_ids)
    domain_transactions = minimize_transactions(balances)

    tx_models: list[SettlementTransactionBase] = [
        SettlementTransactionBase(
            settlement_id=0,
            from_user_id=tx.from_user_id,
            to_user_id=tx.to_user_id,
            amount=tx.amount.amount,
        )
        for tx in domain_transactions
    ]

    if reference_id is None:
        reference_id = generate_reference_id(uow)

    settlement = SettlementBase(
        reference_id=reference_id,
        settled_by_id=settled_by_id,
        settled_at=datetime.now(UTC),
    )

    saved = uow.settlements.save(settlement, expense_ids, tx_models)

    return saved
