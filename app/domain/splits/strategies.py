"""Split calculation strategies for expense sharing.

This module defines the Strategy pattern for calculating how expenses
should be split among group members. Currently only supports even splits,
but designed for extension to uneven splits (percentages, shares) in Epic 4.
"""

from abc import ABC, abstractmethod
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
        # Future: PercentageSplitStrategy, ShareSplitStrategy
    """

    @abstractmethod
    def calculate_shares(
        self,
        expense: ExpensePublic,
        member_ids: list[int],
    ) -> dict[int, Money]:
        """Calculate each member's share of the expense.

        Args:
            expense: The expense to split among members
            member_ids: List of all member user IDs who should share the expense

        Returns:
            Dictionary mapping user_id to their share amount as Money

        Raises:
            InvalidShareError: If shares cannot be calculated (e.g., empty member list)

        Note:
            The sum of all shares should equal the expense amount.
            Rounding errors are handled by the caller (balance calculation).
        """
        ...


class EvenSplitStrategy(SplitStrategy):
    """Split expense evenly among all members.

    Divides the expense amount equally among all provided members.
    Handles rounding by dividing the amount by the number of members.

    Example:
        >>> strategy = EvenSplitStrategy()
        >>> # 100 EUR / 3 people
        >>> shares = strategy.calculate_shares(expense, [1, 2, 3])
        # Returns ~33.33 EUR per person
    """

    def calculate_shares(
        self,
        expense: ExpensePublic,
        member_ids: list[int],
    ) -> dict[int, Money]:
        """Split expense evenly among all members.

        Args:
            expense: The expense to split
            member_ids: All members who should share the expense

        Returns:
            Dictionary with equal share for each member

        Raises:
            InvalidShareError: If member_ids is empty
        """
        from app.domain.errors import InvalidShareError
        from app.domain.value_objects import Money

        if not member_ids:
            raise InvalidShareError("Cannot split expense among zero members")

        # Calculate equal share
        total = Money(expense.amount, expense.currency)
        num_members = len(member_ids)

        # Use exact division (Money will handle it)
        share = total / num_members

        # Create shares dictionary
        shares: dict[int, Money] = {}
        for user_id in member_ids:
            shares[user_id] = share

        return shares
