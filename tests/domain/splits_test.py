"""Tests for split calculation strategies."""

from decimal import Decimal

import pytest

from app.domain.errors import InvalidShareError
from app.domain.models import ExpensePublic, SplitType
from app.domain.splits import (
    EvenSplitStrategy,
    ExactSplitStrategy,
    PercentageSplitStrategy,
    SharesSplitStrategy,
)


def create_expense(
    amount: Decimal,
    payer_id: int = 1,
    group_id: int = 1,
    creator_id: int = 1,
) -> ExpensePublic:
    """Create a test expense."""
    from datetime import date, datetime

    return ExpensePublic(
        id=1,
        group_id=group_id,
        amount=amount,
        description="Test expense",
        date=date.today(),
        creator_id=creator_id,
        payer_id=payer_id,
        currency="EUR",
        split_type=SplitType.EVEN,
        status="PENDING",  # type: ignore
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


class TestEvenSplitStrategy:
    """Tests for EvenSplitStrategy."""

    def test_split_two_people(self):
        """Split 100 EUR evenly between 2 people."""
        strategy = EvenSplitStrategy()
        expense = create_expense(Decimal("100.00"))
        shares = strategy.calculate_shares(expense, [1, 2])

        assert shares[1].amount == Decimal("50.00")
        assert shares[2].amount == Decimal("50.00")
        assert sum(s.amount for s in shares.values()) == Decimal("100.00")

    def test_split_three_people(self):
        """Split 100 EUR evenly between 3 people, remainder to payer."""
        strategy = EvenSplitStrategy()
        expense = create_expense(Decimal("100.00"), payer_id=1)
        shares = strategy.calculate_shares(expense, [1, 2, 3])

        # 100/3 = 33.33 each, but we need 100.00 total
        # Remainder goes to payer (user 1)
        assert shares[1].amount == Decimal("33.34")  # 33.33 + 0.01 remainder
        assert shares[2].amount == Decimal("33.33")
        assert shares[3].amount == Decimal("33.33")
        assert sum(s.amount for s in shares.values()) == Decimal("100.00")

    def test_split_single_person(self):
        """Split with single person - they pay everything."""
        strategy = EvenSplitStrategy()
        expense = create_expense(Decimal("50.00"))
        shares = strategy.calculate_shares(expense, [1])

        assert shares[1].amount == Decimal("50.00")

    def test_empty_member_list_raises_error(self):
        """Split with no members raises InvalidShareError."""
        strategy = EvenSplitStrategy()
        expense = create_expense(Decimal("100.00"))

        with pytest.raises(InvalidShareError, match="zero members"):
            strategy.calculate_shares(expense, [])


class TestSharesSplitStrategy:
    """Tests for SharesSplitStrategy."""

    def test_split_3_to_1(self):
        """Split with 3:1 share ratio."""
        strategy = SharesSplitStrategy()
        expense = create_expense(Decimal("100.00"), payer_id=1)
        shares = strategy.calculate_shares(
            expense,
            [1, 2],
            {1: Decimal("3"), 2: Decimal("1")},
        )

        assert shares[1].amount == Decimal("75.00")
        assert shares[2].amount == Decimal("25.00")
        assert sum(s.amount for s in shares.values()) == Decimal("100.00")

    def test_split_equal_shares(self):
        """Split with equal shares is same as even split."""
        strategy = SharesSplitStrategy()
        expense = create_expense(Decimal("100.00"), payer_id=1)
        shares = strategy.calculate_shares(
            expense,
            [1, 2],
            {1: Decimal("1"), 2: Decimal("1")},
        )

        assert shares[1].amount == Decimal("50.00")
        assert shares[2].amount == Decimal("50.00")

    def test_split_with_remainder(self):
        """Split with remainder distributed to payer."""
        strategy = SharesSplitStrategy()
        expense = create_expense(Decimal("100.00"), payer_id=1)
        # 2:1 ratio on 100 = 66.67 : 33.33 (with rounding)
        shares = strategy.calculate_shares(
            expense,
            [1, 2],
            {1: Decimal("2"), 2: Decimal("1")},
        )

        # 100 * 2/3 = 66.67, 100 * 1/3 = 33.33
        # But 66.67 + 33.33 = 100.00, so no remainder
        assert shares[1].amount == Decimal("66.67")
        assert shares[2].amount == Decimal("33.33")

    def test_missing_share_config_raises_error(self):
        """Missing share config raises ValueError."""
        strategy = SharesSplitStrategy()
        expense = create_expense(Decimal("100.00"))

        with pytest.raises(ValueError, match="Missing share count"):
            strategy.calculate_shares(expense, [1, 2], {1: Decimal("1")})

    def test_no_share_config_raises_error(self):
        """No share config raises ValueError."""
        strategy = SharesSplitStrategy()
        expense = create_expense(Decimal("100.00"))

        with pytest.raises(ValueError, match="requires split_config"):
            strategy.calculate_shares(expense, [1, 2], None)


class TestPercentageSplitStrategy:
    """Tests for PercentageSplitStrategy."""

    def test_split_60_40(self):
        """Split with 60/40 percentage."""
        strategy = PercentageSplitStrategy()
        expense = create_expense(Decimal("100.00"), payer_id=1)
        shares = strategy.calculate_shares(
            expense,
            [1, 2],
            {1: Decimal("60"), 2: Decimal("40")},
        )

        assert shares[1].amount == Decimal("60.00")
        assert shares[2].amount == Decimal("40.00")
        assert sum(s.amount for s in shares.values()) == Decimal("100.00")

    def test_split_three_people(self):
        """Split with three people using percentages."""
        strategy = PercentageSplitStrategy()
        expense = create_expense(Decimal("100.00"), payer_id=1)
        shares = strategy.calculate_shares(
            expense,
            [1, 2, 3],
            {1: Decimal("50"), 2: Decimal("30"), 3: Decimal("20")},
        )

        assert shares[1].amount == Decimal("50.00")
        assert shares[2].amount == Decimal("30.00")
        assert shares[3].amount == Decimal("20.00")

    def test_percentages_must_sum_to_100(self):
        """Percentages that don't sum to 100 raise InvalidShareError."""
        strategy = PercentageSplitStrategy()
        expense = create_expense(Decimal("100.00"))

        with pytest.raises(InvalidShareError, match="sum to 100"):
            strategy.calculate_shares(
                expense,
                [1, 2],
                {1: Decimal("60"), 2: Decimal("30")},  # 90%
            )

    def test_missing_percentage_raises_error(self):
        """Missing percentage raises ValueError."""
        strategy = PercentageSplitStrategy()
        expense = create_expense(Decimal("100.00"))

        with pytest.raises(ValueError, match="Missing percentage"):
            strategy.calculate_shares(
                expense,
                [1, 2],
                {1: Decimal("60")},  # Missing user 2
            )


class TestExactSplitStrategy:
    """Tests for ExactSplitStrategy."""

    def test_split_with_remainder_distribution(self):
        """Exact amounts that sum to total."""
        strategy = ExactSplitStrategy()
        expense = create_expense(Decimal("100.00"), payer_id=1)
        shares = strategy.calculate_shares(
            expense,
            [1, 2],
            {1: Decimal("65.00"), 2: Decimal("35.00")},
        )

        assert shares[1].amount == Decimal("65.00")
        assert shares[2].amount == Decimal("35.00")
        assert sum(s.amount for s in shares.values()) == Decimal("100.00")

    def test_split_three_people(self):
        """Exact amounts for three people."""
        strategy = ExactSplitStrategy()
        expense = create_expense(Decimal("100.00"), payer_id=1)
        shares = strategy.calculate_shares(
            expense,
            [1, 2, 3],
            {1: Decimal("50.00"), 2: Decimal("30.00"), 3: Decimal("20.00")},
        )

        assert shares[1].amount == Decimal("50.00")
        assert shares[2].amount == Decimal("30.00")
        assert shares[3].amount == Decimal("20.00")

    def test_amounts_must_sum_to_total(self):
        """Exact amounts that don't sum to total raise InvalidShareError."""
        strategy = ExactSplitStrategy()
        expense = create_expense(Decimal("100.00"))

        with pytest.raises(InvalidShareError, match="sum to "):
            strategy.calculate_shares(
                expense,
                [1, 2],
                {1: Decimal("60.00"), 2: Decimal("30.00")},  # 90.00
            )

    def test_amounts_exceed_total_raises_error(self):
        """Exact amounts that exceed total raise InvalidShareError."""
        strategy = ExactSplitStrategy()
        expense = create_expense(Decimal("100.00"))

        with pytest.raises(InvalidShareError, match="sum to "):
            strategy.calculate_shares(
                expense,
                [1, 2],
                {1: Decimal("70.00"), 2: Decimal("40.00")},  # 110.00
            )

    def test_missing_amount_raises_error(self):
        """Missing exact amount raises ValueError."""
        strategy = ExactSplitStrategy()
        expense = create_expense(Decimal("100.00"))

        with pytest.raises(ValueError, match="Missing exact amount"):
            strategy.calculate_shares(
                expense,
                [1, 2],
                {1: Decimal("60.00")},  # Missing user 2
            )


class TestDistributeRemainder:
    """Tests for the distribute_remainder helper."""

    def test_positive_remainder_to_payer(self):
        """Positive remainder goes to payer."""
        from app.domain.value_objects import Money

        strategy = EvenSplitStrategy()
        # In this test, shares sum to 66.66 but total is 100
        # So remainder = 100 - 66.66 = 33.34 goes to payer
        shares = {
            1: Money(Decimal("33.33"), "EUR"),
            2: Money(Decimal("33.33"), "EUR"),
        }
        total = Money(Decimal("100.00"), "EUR")

        result = strategy.distribute_remainder(shares, total, payer_id=1)

        # Payer's share = 33.33 + (100 - 66.66) = 33.33 + 33.34 = 66.67
        assert result[1].amount == Decimal("66.67")
        assert result[2].amount == Decimal("33.33")

    def test_negative_remainder_to_payer(self):
        """Negative remainder (from rounding up) goes to payer."""
        from app.domain.value_objects import Money

        strategy = EvenSplitStrategy()
        shares = {
            1: Money(Decimal("33.34"), "EUR"),
            2: Money(Decimal("33.34"), "EUR"),
        }
        total = Money(Decimal("100.00"), "EUR")

        result = strategy.distribute_remainder(shares, total, payer_id=1)

        # Sum is 66.68, total is 100, so we need to handle this case
        # Actually this is an error case - sum should always be <= total
        # Let's adjust the test for a negative remainder case
        shares2 = {
            1: Money(Decimal("50.01"), "EUR"),
            2: Money(Decimal("50.01"), "EUR"),
        }
        total2 = Money(Decimal("100.00"), "EUR")

        result2 = strategy.distribute_remainder(shares2, total2, payer_id=1)

        # Sum is 100.02, total is 100, remainder is -0.02
        assert result2[1].amount == Decimal("49.99")  # 50.01 - 0.02

    def test_no_remainder(self):
        """When shares sum to total, no adjustment needed."""
        from app.domain.value_objects import Money

        strategy = EvenSplitStrategy()
        shares = {
            1: Money(Decimal("50.00"), "EUR"),
            2: Money(Decimal("50.00"), "EUR"),
        }
        total = Money(Decimal("100.00"), "EUR")

        result = strategy.distribute_remainder(shares, total, payer_id=1)

        assert result[1].amount == Decimal("50.00")
        assert result[2].amount == Decimal("50.00")

    def test_payer_not_in_shares(self):
        """If payer isn't in shares, return as-is."""
        from app.domain.value_objects import Money

        strategy = EvenSplitStrategy()
        shares = {
            2: Money(Decimal("33.33"), "EUR"),
            3: Money(Decimal("33.33"), "EUR"),
        }
        total = Money(Decimal("100.00"), "EUR")

        result = strategy.distribute_remainder(shares, total, payer_id=1)

        # Payer 1 not in shares, so no adjustment
        assert 1 not in result
        assert result[2].amount == Decimal("33.33")
        assert result[3].amount == Decimal("33.33")
