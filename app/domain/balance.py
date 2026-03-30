"""Balance calculation domain logic.

Pure functions for calculating member balances and minimizing settlement transactions.
Works with any number of group members (2, 3, N).

All functions are pure (no side effects, no I/O) making them easy to test.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.domain.value_objects import Money

if TYPE_CHECKING:
    from app.domain.models import ExpensePublic


@dataclass(frozen=True)
class MemberBalance:
    """Balance summary for a single member.

    Immutable balance information showing how much a member paid,
    their fair share, and their net position (owed or owes).

    Attributes:
        user_id: Member's user ID
        amount_paid: Total amount this member paid
        fair_share: What they should have paid (their share of total)
        net_balance: Positive = owed money, Negative = owes money

    Example:
        >>> balance = MemberBalance(
        ...     user_id=1,
        ...     amount_paid=Money(Decimal("100.00")),
        ...     fair_share=Money(Decimal("50.00")),
        ...     net_balance=Money(Decimal("50.00"))
        ... )
        >>> balance.is_owed
        True
        >>> balance.net_balance.amount
        Decimal('50.00')
    """

    user_id: int
    amount_paid: Money
    fair_share: Money
    net_balance: Money

    @property
    def is_owed(self) -> bool:
        """True if this member is owed money (positive balance)."""
        return self.net_balance.amount > 0

    @property
    def owes(self) -> bool:
        """True if this member owes money (negative balance)."""
        return self.net_balance.amount < 0

    @property
    def is_settled(self) -> bool:
        """True if balance is zero (all square)."""
        return self.net_balance.amount == 0


@dataclass(frozen=True)
class SettlementTransaction:
    """A single transaction to settle debts.

    Represents one payment from a debtor to a creditor.
    Multiple transactions may be needed to settle all balances.

    Attributes:
        from_user_id: User ID of the debtor (payer)
        to_user_id: User ID of the creditor (recipient)
        amount: Amount to be transferred

    Example:
        >>> tx = SettlementTransaction(
        ...     from_user_id=2,  # Bob owes money
        ...     to_user_id=1,    # Alice is owed money
        ...     amount=Money(Decimal("50.00"))
        ... )
    """

    from_user_id: int
    to_user_id: int
    amount: Money


def calculate_balances_from_splits(
    expenses: list[ExpensePublic],
    splits_by_expense: dict[int, list[tuple[int, Decimal]]],
    member_ids: list[int],
) -> dict[int, MemberBalance]:
    """Calculate balances using pre-loaded split amounts.

    This is the canonical balance calculation that respects all split types
    (even, percentage, shares, exact) by reading persisted split rows rather
    than re-deriving them. Used by both the dashboard and settlement flows.

    Args:
        expenses: List of expenses to calculate from
        splits_by_expense: {expense_id: [(user_id, amount), ...]} from expense_splits table
        member_ids: All user IDs in the household

    Returns:
        Dictionary mapping user_id to MemberBalance
    """
    from app.domain.value_objects import Money

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

        for user_id, split_amount in splits_by_expense.get(expense.id, []):
            if user_id in fair_share:
                fair_share[user_id] += split_amount

    result: dict[int, MemberBalance] = {}
    for uid in member_ids:
        paid = Money(amount_paid[uid], currency)
        owed = Money(fair_share[uid], currency)
        net = Money(amount_paid[uid] - fair_share[uid], currency)
        result[uid] = MemberBalance(uid, paid, owed, net)

    return result


def minimize_transactions(balances: dict[int, MemberBalance]) -> list[SettlementTransaction]:
    """Minimize number of transactions to settle all debts.

    Uses a greedy algorithm that matches the largest debtor with the
    largest creditor. This produces at most N-1 transactions for N people.

    For 2-person groups, this is optimal. For N-person groups, it may
    not be globally optimal but is simple and produces reasonable results.

    Args:
        balances: Member balances from calculate_balances()

    Returns:
        List of SettlementTransaction to settle all debts

    Example:
        >>> balances = calculate_balances(expenses, member_ids, config)
        >>> transactions = minimize_transactions(balances)
        >>> len(transactions)
        2  # At most len(member_ids) - 1
    """
    if not balances:
        return []

    # Separate debtors (negative net = owes money) and creditors (positive = owed)
    debtors: list[tuple[int, Money]] = []  # (user_id, amount_owed)
    creditors: list[tuple[int, Money]] = []  # (user_id, amount_owed)

    for user_id, balance in balances.items():
        net = balance.net_balance
        if net.amount < 0:
            # Negative net = owes money (debtor)
            debtors.append((user_id, net.abs()))
        elif net.amount > 0:
            # Positive net = is owed money (creditor)
            creditors.append((user_id, net))

    # If no debtors or no creditors, everyone is settled
    if not debtors or not creditors:
        return []

    # Sort by amount (descending) - greedy approach
    debtors.sort(key=lambda x: x[1].amount, reverse=True)
    creditors.sort(key=lambda x: x[1].amount, reverse=True)

    transactions: list[SettlementTransaction] = []

    # Greedy matching: largest debtor pays largest creditor
    while debtors and creditors:
        debtor_id, debt_amount = debtors[0]
        creditor_id, credit_amount = creditors[0]

        # Transaction amount is min of remaining debt and credit
        transaction_amount = debt_amount if debt_amount < credit_amount else credit_amount

        transactions.append(
            SettlementTransaction(
                from_user_id=debtor_id,
                to_user_id=creditor_id,
                amount=transaction_amount,
            )
        )

        # Update remaining amounts
        remaining_debt = debt_amount - transaction_amount
        remaining_credit = credit_amount - transaction_amount

        # Remove settled parties or update remaining amounts
        if remaining_debt.amount == 0:
            debtors.pop(0)
        else:
            debtors[0] = (debtor_id, remaining_debt)

        if remaining_credit.amount == 0:
            creditors.pop(0)
        else:
            creditors[0] = (creditor_id, remaining_credit)

    return transactions
