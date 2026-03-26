"""Split calculation strategies for expense sharing.

This module defines the Strategy pattern for calculating how expenses
should be split among group members. Supports four split types:
- EVEN: Equal split among all participants
- SHARES: Weighted split based on share counts
- PERCENTAGE: Split based on percentages (must sum to 100%)
- EXACT: Exact amounts specified per person (must sum to total)
"""

from abc import ABC, abstractmethod
from decimal import ROUND_HALF_EVEN, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.models import ExpensePublic
    from app.domain.value_objects import Money


class SplitStrategy(ABC):
    """Abstract base class for expense splitting strategies.

    Implementations define how a single expense should be divided among
    group members. The strategy is called per-expense during balance calculation.

    Example:
        >>> strategy = EvenSplitStrategy()
        >>> expense = ExpensePublic(amount=Decimal("100.00"), ...)
        >>> shares = strategy.calculate_shares(expense, [1, 2, 3])
        >>> shares
        {1: Money(amount=Decimal('33.33'), currency='EUR'),
         2: Money(amount=Decimal('33.33'), currency='EUR'),
         3: Money(amount=Decimal('33.34'), currency='EUR')}

    See Also:
        EvenSplitStrategy: Equal split among all members
        SharesSplitStrategy: Weighted split based on share counts
        PercentageSplitStrategy: Split based on percentages
        ExactSplitStrategy: Exact amounts per person
    """

    @abstractmethod
    def calculate_shares(
        self,
        expense: ExpensePublic,
        member_ids: list[int],
        split_config: dict[int, Decimal] | None = None,
    ) -> dict[int, Money]:
        """Calculate each member's share of the expense.

        Args:
            expense: The expense to split among members
            member_ids: List of all member user IDs who should share the expense
            split_config: Optional configuration for split values:
                - SHARES: dict[user_id, share_count]
                - PERCENTAGE: dict[user_id, percentage] (as Decimal, e.g., Decimal("60") for 60%)
                - EXACT: dict[user_id, exact_amount]

        Returns:
            Dictionary mapping user_id to their share amount as Money

        Raises:
            InvalidShareError: If shares cannot be calculated (e.g., empty member list)
            ValueError: If split_config is invalid for the strategy
        """
        ...

    @staticmethod
    def distribute_remainder(
        shares: dict[int, Money],
        total: Money,
        payer_id: int,
    ) -> dict[int, Money]:
        """Distribute rounding remainder to the payer.

        After calculating shares, the sum may be slightly different from
        the total due to rounding. This method adjusts by giving the
        remainder (positive or negative) to the payer.

        Args:
            shares: Dictionary of user_id to their calculated share
            total: The original total amount
            payer_id: The user ID who paid for the expense

        Returns:
            Dictionary with adjusted shares

        Example:
            >>> shares = {1: Money(Decimal('33.33'), 'EUR'), 2: Money(Decimal('33.33'), 'EUR')}
            >>> total = Money(Decimal('100.00'), 'EUR')
            >>> distribute_remainder(shares, total, payer_id=1)
            {1: Money(Decimal('33.34'), 'EUR'), 2: Money(Decimal('33.33'), 'EUR')}
        """
        from app.domain.value_objects import Money

        if payer_id not in shares:
            return shares

        # Calculate sum of all shares
        share_sum = sum(s.amount for s in shares.values())
        remainder = total.amount - share_sum

        # If there's a remainder, add it to the payer's share
        if remainder != 0:
            adjusted_shares = dict(shares)
            adjusted_shares[payer_id] = Money(
                shares[payer_id].amount + remainder,
                total.currency,
            )
            return adjusted_shares

        return shares


class EvenSplitStrategy(SplitStrategy):
    """Split expense evenly among all members.

    Divides the expense amount equally among all provided members.
    Handles rounding by distributing remainder to the payer.

    Example:
        >>> strategy = EvenSplitStrategy()
        >>> # 100 EUR / 3 people
        >>> shares = strategy.calculate_shares(expense, [1, 2, 3])
        # Returns ~33.33 EUR per person, with remainder to payer
    """

    def calculate_shares(
        self,
        expense: ExpensePublic,
        member_ids: list[int],
        split_config: dict[int, Decimal] | None = None,
    ) -> dict[int, Money]:
        """Split expense evenly among all members.

        Args:
            expense: The expense to split
            member_ids: All members who should share the expense
            split_config: Ignored for even split

        Returns:
            Dictionary with equal share for each member

        Raises:
            InvalidShareError: If member_ids is empty
        """
        from app.domain.errors import InvalidShareError
        from app.domain.value_objects import Money

        if not member_ids:
            raise InvalidShareError("Cannot split expense among zero members")

        # Calculate equal share (use exact division, Money handles it)
        total = Money(expense.amount, expense.currency)
        num_members = len(member_ids)

        # Calculate base share with proper rounding
        base_share_amount = (total.amount / num_members).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_EVEN
        )
        base_share = Money(base_share_amount, expense.currency)

        # Create shares dictionary
        shares: dict[int, Money] = {}
        for user_id in member_ids:
            shares[user_id] = base_share

        # Distribute remainder to payer
        return self.distribute_remainder(shares, total, expense.payer_id)


class SharesSplitStrategy(SplitStrategy):
    """Split expense based on weighted share counts.

    Each member gets a portion proportional to their share count.
    Example: If A has 3 shares and B has 1 share, A gets 75% and B gets 25%.

    Example:
        >>> strategy = SharesSplitStrategy()
        >>> expense = ExpensePublic(amount=Decimal("100.00"), payer_id=1, ...)
        >>> split_config = {1: Decimal("3"), 2: Decimal("1")}  # 3:1 split
        >>> shares = strategy.calculate_shares(expense, [1, 2], split_config)
        # Returns {1: 75.00 EUR, 2: 25.00 EUR} with remainder to payer
    """

    def calculate_shares(
        self,
        expense: ExpensePublic,
        member_ids: list[int],
        split_config: dict[int, Decimal] | None = None,
    ) -> dict[int, Money]:
        """Split expense based on share counts.

        Args:
            expense: The expense to split
            member_ids: All members who should share the expense
            split_config: dict[user_id, share_count]

        Returns:
            Dictionary with weighted share for each member

        Raises:
            InvalidShareError: If member_ids is empty or split_config is missing
            ValueError: If split_config doesn't cover all members
        """
        from app.domain.errors import InvalidShareError
        from app.domain.value_objects import Money

        if not member_ids:
            raise InvalidShareError("Cannot split expense among zero members")

        if not split_config:
            raise ValueError("Shares split requires split_config with share counts")

        # Validate all members have share counts
        for user_id in member_ids:
            if user_id not in split_config:
                raise ValueError(f"Missing share count for user {user_id}")

        total = Money(expense.amount, expense.currency)
        total_shares = sum(split_config[user_id] for user_id in member_ids)

        if total_shares <= 0:
            raise InvalidShareError("Total shares must be positive")

        # Calculate each member's share
        shares: dict[int, Money] = {}
        for user_id in member_ids:
            share_count = split_config[user_id]
            share_amount = (total.amount * share_count / total_shares).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_EVEN
            )
            shares[user_id] = Money(share_amount, expense.currency)

        # Distribute remainder to payer
        return self.distribute_remainder(shares, total, expense.payer_id)


class PercentageSplitStrategy(SplitStrategy):
    """Split expense based on percentages.

    Each member gets a portion based on their percentage.
    Percentages must sum to exactly 100%.

    Example:
        >>> strategy = PercentageSplitStrategy()
        >>> expense = ExpensePublic(amount=Decimal("100.00"), payer_id=1, ...)
        >>> split_config = {1: Decimal("60"), 2: Decimal("40")}  # 60/40 split
        >>> shares = strategy.calculate_shares(expense, [1, 2], split_config)
        # Returns {1: 60.00 EUR, 2: 40.00 EUR}
    """

    def calculate_shares(
        self,
        expense: ExpensePublic,
        member_ids: list[int],
        split_config: dict[int, Decimal] | None = None,
    ) -> dict[int, Money]:
        """Split expense based on percentages.

        Args:
            expense: The expense to split
            member_ids: All members who should share the expense
            split_config: dict[user_id, percentage] (e.g., Decimal("60") for 60%)

        Returns:
            Dictionary with percentage-based share for each member

        Raises:
            InvalidShareError: If member_ids is empty or percentages don't sum to 100
            ValueError: If split_config is missing or doesn't cover all members
        """
        from app.domain.errors import InvalidShareError
        from app.domain.value_objects import Money

        if not member_ids:
            raise InvalidShareError("Cannot split expense among zero members")

        if not split_config:
            raise ValueError("Percentage split requires split_config with percentages")

        # Validate all members have percentages
        for user_id in member_ids:
            if user_id not in split_config:
                raise ValueError(f"Missing percentage for user {user_id}")

        # Validate percentages sum to 100
        total_percentage = sum(split_config[user_id] for user_id in member_ids)
        if total_percentage != Decimal("100"):
            raise InvalidShareError(f"Percentages must sum to 100, got {total_percentage}")

        total = Money(expense.amount, expense.currency)

        # Calculate each member's share
        shares: dict[int, Money] = {}
        for user_id in member_ids:
            percentage = split_config[user_id]
            share_amount = (total.amount * percentage / 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_EVEN
            )
            shares[user_id] = Money(share_amount, expense.currency)

        # Distribute remainder to payer
        return self.distribute_remainder(shares, total, expense.payer_id)


class ExactSplitStrategy(SplitStrategy):
    """Split expense with exact amounts per person.

    Each member pays a specific amount. All amounts must sum to the
    expense total exactly.

    Example:
        >>> strategy = ExactSplitStrategy()
        >>> expense = ExpensePublic(amount=Decimal("100.00"), payer_id=1, ...)
        >>> split_config = {1: Decimal("65.00"), 2: Decimal("35.00")}
        >>> shares = strategy.calculate_shares(expense, [1, 2], split_config)
        # Returns {1: 65.00 EUR, 2: 35.00 EUR}
    """

    def calculate_shares(
        self,
        expense: ExpensePublic,
        member_ids: list[int],
        split_config: dict[int, Decimal] | None = None,
    ) -> dict[int, Money]:
        """Split expense with exact amounts.

        Args:
            expense: The expense to split
            member_ids: All members who should share the expense
            split_config: dict[user_id, exact_amount]

        Returns:
            Dictionary with exact share for each member

        Raises:
            InvalidShareError: If amounts don't sum to expense total
            ValueError: If split_config is missing or doesn't cover all members
        """
        from app.domain.errors import InvalidShareError
        from app.domain.value_objects import Money

        if not member_ids:
            raise InvalidShareError("Cannot split expense among zero members")

        if not split_config:
            raise ValueError("Exact split requires split_config with exact amounts")

        # Validate all members have amounts
        for user_id in member_ids:
            if user_id not in split_config:
                raise ValueError(f"Missing exact amount for user {user_id}")

        total = Money(expense.amount, expense.currency)

        # Calculate sum of exact amounts
        exact_sum = sum(split_config[user_id] for user_id in member_ids)

        # Validate amounts sum to total
        if exact_sum != total.amount:
            raise InvalidShareError(f"Exact amounts must sum to {total.amount}, got {exact_sum}")

        # Create shares dictionary
        shares: dict[int, Money] = {}
        for user_id in member_ids:
            shares[user_id] = Money(split_config[user_id], expense.currency)

        # No remainder distribution for exact split (already exact)
        return shares
