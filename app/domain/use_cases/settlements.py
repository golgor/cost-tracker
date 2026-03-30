"""Settlement domain use cases."""

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.balance import (
    MemberBalance,
    SettlementTransaction,
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
from app.domain.value_objects import Money


def _calculate_balances_from_splits(
    uow: UnitOfWorkPort,
    expenses: list[ExpensePublic],
    member_ids: list[int],
) -> dict[int, MemberBalance]:
    """Calculate balances using persisted split rows, not re-derived splits.

    This respects the actual split type and amounts stored in expense_splits,
    so percentage/shares/exact splits settle correctly.
    """
    if not expenses:
        currency = "EUR"
        zero = Money(Decimal("0"), currency)
        return {uid: MemberBalance(uid, zero, zero, zero) for uid in member_ids}

    currency = expenses[0].currency

    amount_paid: dict[int, Decimal] = {uid: Decimal("0") for uid in member_ids}
    fair_share: dict[int, Decimal] = {uid: Decimal("0") for uid in member_ids}

    for expense in expenses:
        if expense.payer_id in amount_paid:
            amount_paid[expense.payer_id] += expense.amount

        splits = uow.expenses.get_splits(expense.id)
        for split in splits:
            if split.user_id in fair_share:
                fair_share[split.user_id] += split.amount

    result: dict[int, MemberBalance] = {}
    for uid in member_ids:
        paid = Money(amount_paid[uid], currency)
        owed = Money(fair_share[uid], currency)
        net = Money(amount_paid[uid] - fair_share[uid], currency)
        result[uid] = MemberBalance(uid, paid, owed, net)

    return result


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
    expenses: list[ExpensePublic] = []
    for expense_id in expense_ids:
        expense = uow.expenses.get_by_id(expense_id)
        if expense is None:
            raise SettlementError(f"Expense {expense_id} no longer exists")
        if expense.status == ExpenseStatus.SETTLED:
            raise StaleExpenseError(expense_id)
        expenses.append(expense)

    balances = _calculate_balances_from_splits(uow, expenses, member_ids)
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

    expenses: list[ExpensePublic] = []
    for expense_id in expense_ids:
        expense = uow.expenses.get_by_id(expense_id)
        if expense is None:
            raise SettlementError(f"Expense {expense_id} no longer exists")
        if expense.status == ExpenseStatus.SETTLED:
            raise StaleExpenseError(expense_id)
        expenses.append(expense)

    balances = _calculate_balances_from_splits(uow, expenses, member_ids)
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
