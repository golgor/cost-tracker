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
    from app.domain.splits.config import BalanceConfig
    from app.domain.splits.strategies import SplitStrategy


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


def calculate_balances(
    expenses: list[ExpensePublic],
    member_ids: list[int],
    config: BalanceConfig,
    strategy: SplitStrategy | None = None,
) -> dict[int, MemberBalance]:
    """Calculate balances for all group members.

    Computes how much each member paid vs. their fair share, resulting
    in net balances (positive = owed money, negative = owes money).

    The calculation works for any number of members (2, 3, N) and uses
    the provided split strategy to determine fair shares.

    Args:
        expenses: List of pending expenses to calculate from
        member_ids: All member user IDs in the group
        config: Rounding configuration (precision, mode)
        strategy: Split strategy (default: EvenSplitStrategy)

    Returns:
        Dictionary mapping user_id to MemberBalance

    Raises:
        CurrencyMismatchError: If expenses have different currencies
        InvalidShareError: If share calculation fails

    Example:
        >>> expenses = [ExpensePublic(amount=Decimal("100.00"), payer_id=1, ...)]
        >>> member_ids = [1, 2, 3]
        >>> config = BalanceConfig()
        >>> balances = calculate_balances(expenses, member_ids, config)
        >>> balances[1].net_balance.amount  # Payer is owed
        Decimal('33.34')
        >>> balances[2].net_balance.amount  # Others owe
        Decimal('-33.33')
    """
    from app.domain.errors import CurrencyMismatchError, InvalidShareError
    from app.domain.splits.strategies import EvenSplitStrategy
    from app.domain.value_objects import Money

    # Validate inputs
    if not member_ids:
        raise InvalidShareError("Cannot calculate balances for empty group")

    if not expenses:
        # No expenses means everyone has zero balance
        currency = "EUR"  # Default
        zero = Money(Decimal("0"), currency)
        return {user_id: MemberBalance(user_id, zero, zero, zero) for user_id in member_ids}

    # Validate all expenses have same currency
    currencies = {e.currency for e in expenses}
    if len(currencies) > 1:
        raise CurrencyMismatchError(currencies)

    currency = next(iter(currencies))

    # Use default strategy if none provided
    if strategy is None:
        strategy = EvenSplitStrategy()

    # Initialize tracking for each member
    amount_paid: dict[int, Money] = {uid: Money(Decimal("0"), currency) for uid in member_ids}
    fair_share: dict[int, Money] = {uid: Money(Decimal("0"), currency) for uid in member_ids}

    # Process each expense
    for expense in expenses:
        # Track how much each person paid
        payer_id = expense.payer_id
        if payer_id in amount_paid:
            expense_amount = Money(expense.amount, expense.currency)
            amount_paid[payer_id] = amount_paid[payer_id] + expense_amount

        # Calculate fair shares using strategy
        try:
            shares = strategy.calculate_shares(expense, member_ids)
        except Exception as e:
            raise InvalidShareError(
                f"Failed to calculate shares for expense {expense.id}: {e}"
            ) from e

        # Accumulate fair share for each member
        for user_id, share in shares.items():
            if user_id in fair_share:
                fair_share[user_id] = fair_share[user_id] + share

    # Build MemberBalance for each member
    result: dict[int, MemberBalance] = {}
    for user_id in member_ids:
        paid = amount_paid[user_id]
        owed = fair_share[user_id]
        net = paid - owed

        # Apply rounding according to config
        paid_rounded = _round_money(paid, config)
        owed_rounded = _round_money(owed, config)
        net_rounded = _round_money(net, config)

        result[user_id] = MemberBalance(
            user_id=user_id,
            amount_paid=paid_rounded,
            fair_share=owed_rounded,
            net_balance=net_rounded,
        )

    # Handle rounding errors: ensure sum of net balances equals zero
    _adjust_rounding_errors(result, member_ids, config)

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


def _round_money(money: Money, config: BalanceConfig) -> Money:
    """Round Money according to configuration.

    Args:
        money: Money to round
        config: BalanceConfig with rounding settings

    Returns:
        Rounded Money
    """
    rounded = money.amount.quantize(config.rounding_precision, rounding=config.rounding_mode)
    return Money(rounded, money.currency)


def _adjust_rounding_errors(
    balances: dict[int, MemberBalance],
    member_ids: list[int],
    config: BalanceConfig,
) -> None:
    """Adjust rounding errors to ensure sum of net balances equals zero.

    Due to rounding, the sum of all net balances may not exactly equal zero
    (e.g., 33.33 + 33.33 + 33.34 = 100.00, but net balances sum to 0.01).

    This function adjusts the largest net balance (typically the payer)
    to absorb any rounding discrepancy by adjusting their fair share.

    Args:
        balances: Dictionary of MemberBalance (modified in place via dict replacement)
        member_ids: List of member IDs in input order
        config: BalanceConfig
    """
    currency = next(iter(balances.values())).net_balance.currency

    total_amount = sum(b.net_balance.amount for b in balances.values())
    if total_amount == 0:
        return

    # Find member with largest absolute net balance to absorb error
    # Prefer the first member in the list (typically the payer)
    max_user_id = max(
        balances.keys(),
        key=lambda uid: (abs(balances[uid].net_balance.amount), -member_ids.index(uid)),
    )

    old_balance = balances[max_user_id]
    new_net_balance = Money(old_balance.net_balance.amount - total_amount, currency)
    new_fair_share = Money(old_balance.amount_paid.amount - new_net_balance.amount, currency)

    balances[max_user_id] = MemberBalance(
        user_id=max_user_id,
        amount_paid=old_balance.amount_paid,
        fair_share=_round_money(new_fair_share, config),
        net_balance=_round_money(new_net_balance, config),
    )
