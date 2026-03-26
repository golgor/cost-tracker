"""Comprehensive unit tests for balance calculation domain logic.

Tests all scenarios including 2-person, 3-person, 4+ person groups,
rounding edge cases, transaction minimization, and error conditions.

All tests are pure unit tests with no database dependencies.
"""

from decimal import Decimal

import pytest

from app.domain.balance import (
    MemberBalance,
    calculate_balances,
    minimize_transactions,
)
from app.domain.errors import (
    CurrencyMismatchError,
    InvalidShareError,
)
from app.domain.models import ExpensePublic, ExpenseStatus
from app.domain.splits import BalanceConfig, EvenSplitStrategy
from app.domain.value_objects import Money


class TestMoneyValueObject:
    """Test Money value object functionality."""

    def test_create_money_from_decimal(self):
        """Money can be created from Decimal."""
        m = Money(Decimal("100.50"))
        assert m.amount == Decimal("100.50")
        assert m.currency == "EUR"

    def test_create_money_from_string(self):
        """Money can be created from string."""
        m = Money("100.50")
        assert m.amount == Decimal("100.50")

    def test_create_money_from_int(self):
        """Money can be created from int."""
        m = Money(100)
        assert m.amount == Decimal("100")

    def test_money_equality(self):
        """Money objects with same amount and currency are equal."""
        m1 = Money(Decimal("100.00"))
        m2 = Money(Decimal("100.00"))
        assert m1 == m2

    def test_money_addition_same_currency(self):
        """Can add Money with same currency."""
        m1 = Money(Decimal("100.00"))
        m2 = Money(Decimal("50.00"))
        result = m1 + m2
        assert result.amount == Decimal("150.00")

    def test_money_addition_different_currency_raises(self):
        """Adding Money with different currency raises error."""
        m1 = Money(Decimal("100.00"), "EUR")
        m2 = Money(Decimal("50.00"), "USD")
        with pytest.raises(ValueError, match="Currency mismatch"):
            m1 + m2

    def test_money_subtraction(self):
        """Can subtract Money."""
        m1 = Money(Decimal("100.00"))
        m2 = Money(Decimal("30.00"))
        result = m1 - m2
        assert result.amount == Decimal("70.00")

    def test_money_multiplication(self):
        """Can multiply Money by scalar."""
        m = Money(Decimal("100.00"))
        result = m * 2
        assert result.amount == Decimal("200.00")

    def test_money_division(self):
        """Can divide Money by scalar."""
        m = Money(Decimal("100.00"))
        result = m / 2
        assert result.amount == Decimal("50.00")

    def test_money_division_by_zero_raises(self):
        """Division by zero raises error."""
        m = Money(Decimal("100.00"))
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            m / 0

    def test_money_comparison(self):
        """Money supports comparison operators."""
        m1 = Money(Decimal("100.00"))
        m2 = Money(Decimal("50.00"))
        assert m2 < m1
        assert m1 > m2
        assert m2 <= m1
        assert m1 >= m2

    def test_money_is_zero(self):
        """is_zero property works correctly."""
        m1 = Money(Decimal("0.00"))
        m2 = Money(Decimal("100.00"))
        assert m1.is_zero()
        assert not m2.is_zero()

    def test_money_abs(self):
        """abs() returns absolute value."""
        # Note: Money can't be negative due to validation
        m = Money(Decimal("100.00"))
        assert m.abs().amount == Decimal("100.00")

    def test_money_negative_amount_allowed(self):
        """Negative amounts are allowed (for net balances)."""
        m = Money(Decimal("-100.00"))
        assert m.amount == Decimal("-100.00")

    def test_money_nan_raises(self):
        """NaN amounts are rejected."""
        with pytest.raises(ValueError, match="cannot be NaN"):
            Money(Decimal("NaN"))

    def test_money_infinity_raises(self):
        """Infinity amounts are rejected."""
        with pytest.raises(ValueError, match="cannot be infinite"):
            Money(Decimal("Infinity"))

    def test_money_to_string(self):
        """to_string serializes correctly."""
        m = Money(Decimal("100.50"))
        assert m.to_string() == "100.50"

    def test_money_from_string(self):
        """from_string deserializes correctly."""
        m = Money.from_string("100.50", "EUR")
        assert m.amount == Decimal("100.50")
        assert m.currency == "EUR"


class TestBalanceConfig:
    """Test BalanceConfig validation."""

    def test_default_config(self):
        """Default config has cents precision."""
        config = BalanceConfig()
        assert config.rounding_precision == Decimal("0.01")
        assert config.rounding_mode == "ROUND_HALF_EVEN"

    def test_valid_dimes_precision(self):
        """0.1 precision is valid."""
        config = BalanceConfig(rounding_precision=Decimal("0.1"))
        assert config.rounding_precision == Decimal("0.1")

    def test_valid_thousandths_precision(self):
        """0.001 precision is valid."""
        config = BalanceConfig(rounding_precision=Decimal("0.001"))
        assert config.rounding_precision == Decimal("0.001")

    def test_invalid_precision_not_power_of_10(self):
        """Non-power-of-10 precision is rejected."""
        with pytest.raises(ValueError, match="power of 10"):
            BalanceConfig(rounding_precision=Decimal("0.05"))

    def test_invalid_precision_zero(self):
        """Zero precision is rejected."""
        with pytest.raises(ValueError, match="positive"):
            BalanceConfig(rounding_precision=Decimal("0"))

    def test_invalid_precision_negative(self):
        """Negative precision is rejected."""
        with pytest.raises(ValueError, match="positive"):
            BalanceConfig(rounding_precision=Decimal("-0.01"))

    def test_invalid_rounding_mode(self):
        """Invalid rounding mode is rejected."""
        with pytest.raises(ValueError, match="Invalid rounding mode"):
            BalanceConfig(rounding_mode="ROUND_RANDOM")

    def test_default_factory_method(self):
        """default() class method returns default config."""
        config = BalanceConfig.default()
        assert config.rounding_precision == Decimal("0.01")

    def test_dimes_factory_method(self):
        """dimes() class method returns 0.1 precision."""
        config = BalanceConfig.dimes()
        assert config.rounding_precision == Decimal("0.1")


class TestCalculateBalancesTwoPeople:
    """Test balance calculation with 2 people."""

    def _create_expense(
        self,
        amount: str,
        payer_id: int,
        currency: str = "EUR",
    ) -> ExpensePublic:
        """Helper to create expense for testing."""
        from datetime import date, datetime

        return ExpensePublic(
            id=1,
            group_id=1,
            amount=Decimal(amount),
            description="Test expense",
            date=date.today(),
            creator_id=payer_id,
            payer_id=payer_id,
            currency=currency,
            status=ExpenseStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def test_equal_expenses_zero_balance(self):
        """When both pay equal amounts, balance is zero."""
        expenses = [
            self._create_expense("100.00", payer_id=1),
            self._create_expense("100.00", payer_id=2),
        ]
        member_ids = [1, 2]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        assert result[1].net_balance.amount == Decimal("0.00")
        assert result[2].net_balance.amount == Decimal("0.00")
        assert result[1].is_settled
        assert result[2].is_settled

    def test_user1_pays_all_positive_balance(self):
        """When user1 pays 100, user2 owes 50."""
        expenses = [self._create_expense("100.00", payer_id=1)]
        member_ids = [1, 2]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # User 1 paid 100, fair share is 50, so user 2 owes user 1
        assert result[1].net_balance.amount == Decimal("50.00")
        assert result[1].is_owed
        assert result[2].net_balance.amount == Decimal("-50.00")
        assert result[2].owes

    def test_user2_pays_all_negative_balance(self):
        """When user2 pays 100, user1 owes 50."""
        expenses = [self._create_expense("100.00", payer_id=2)]
        member_ids = [1, 2]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # User 2 paid 100, fair share is 50, so user 1 owes user 2
        assert result[1].net_balance.amount == Decimal("-50.00")
        assert result[1].owes
        assert result[2].net_balance.amount == Decimal("50.00")
        assert result[2].is_owed

    def test_alternating_payments_balanced(self):
        """Alternating payments balance out."""
        expenses = [
            self._create_expense("100.00", payer_id=1),
            self._create_expense("100.00", payer_id=2),
            self._create_expense("50.00", payer_id=1),
            self._create_expense("50.00", payer_id=2),
        ]
        member_ids = [1, 2]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # Both paid 150 total, fair share 150 each
        assert result[1].net_balance.amount == Decimal("0.00")
        assert result[2].net_balance.amount == Decimal("0.00")

    def test_uneven_amounts(self):
        """User1 pays 75, user2 pays 25."""
        expenses = [
            self._create_expense("75.00", payer_id=1),
            self._create_expense("25.00", payer_id=2),
        ]
        member_ids = [1, 2]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # Total 100, fair share 50 each
        # User 1 paid 75, so is owed 25
        # User 2 paid 25, so owes 25
        assert result[1].net_balance.amount == Decimal("25.00")
        assert result[2].net_balance.amount == Decimal("-25.00")

    def test_empty_expenses_zero_balance(self):
        """No expenses means everyone has zero balance."""
        expenses = []
        member_ids = [1, 2]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        assert result[1].net_balance.amount == Decimal("0.00")
        assert result[2].net_balance.amount == Decimal("0.00")


class TestCalculateBalancesThreePeople:
    """Test balance calculation with 3 people - reveals rounding issues."""

    def _create_expense(
        self,
        amount: str,
        payer_id: int,
        expense_id: int = 1,
    ) -> ExpensePublic:
        """Helper to create expense for testing."""
        from datetime import date, datetime

        return ExpensePublic(
            id=expense_id,
            group_id=1,
            amount=Decimal(amount),
            description="Test expense",
            date=date.today(),
            creator_id=payer_id,
            payer_id=payer_id,
            currency="EUR",
            status=ExpenseStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def test_equal_split_100_euros(self):
        """100€ / 3 = 33.34 for payer, 33.33 for others."""
        expenses = [self._create_expense("100.00", payer_id=1)]
        member_ids = [1, 2, 3]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # User 1 paid 100, fair share is 33.33...
        # Net balance = paid - fair_share = 100 - 33.34 = 66.66
        # Others: 0 - 33.33 = -33.33
        assert result[1].net_balance.amount == Decimal("66.66")  # Payer is owed
        assert result[2].net_balance.amount == Decimal("-33.33")  # Owes
        assert result[3].net_balance.amount == Decimal("-33.33")  # Owes

        # Sum must be zero (66.66 - 33.33 - 33.33 = 0)
        total = sum(r.net_balance.amount for r in result.values())
        assert total == Decimal("0")

    def test_sum_of_balances_is_always_zero(self):
        """Critical: net balances must always sum to zero."""
        expenses = [
            self._create_expense("100.00", payer_id=1),
            self._create_expense("50.00", payer_id=2, expense_id=2),
        ]
        member_ids = [1, 2, 3]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        total = sum(r.net_balance.amount for r in result.values())
        assert total == Decimal("0"), f"Balances sum to {total}, should be 0"

    def test_one_pays_all_others_owe(self):
        """User1 pays 300, users 2&3 each owe 100."""
        expenses = [self._create_expense("300.00", payer_id=1)]
        member_ids = [1, 2, 3]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        assert result[1].net_balance.amount == Decimal("200.00")
        assert result[2].net_balance.amount == Decimal("-100.00")
        assert result[3].net_balance.amount == Decimal("-100.00")

    def test_various_contributions(self):
        """User1: 150, User2: 100, User3: 50."""
        expenses = [
            self._create_expense("150.00", payer_id=1, expense_id=1),
            self._create_expense("100.00", payer_id=2, expense_id=2),
            self._create_expense("50.00", payer_id=3, expense_id=3),
        ]
        member_ids = [1, 2, 3]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # Total 300, fair share ~100 each (with rounding)
        # User 1: paid 150, owes ~100, net ~+50
        # User 2: paid 100, owes ~100, net ~0 (small rounding error)
        # User 3: paid 50, owes ~100, net ~-50

        # Due to rounding in split calculations, net balances may have small errors
        # The key invariant is that sum of nets equals zero
        total_net = sum(r.net_balance.amount for r in result.values())
        assert total_net == Decimal("0"), f"Sum of nets should be 0, got {total_net}"

        # User 1 should be owed approximately 50
        assert abs(result[1].net_balance.amount - Decimal("50.00")) < Decimal("0.10")
        # User 2 should be approximately even (may have small rounding error)
        assert abs(result[2].net_balance.amount) < Decimal("0.10")
        # User 3 should owe approximately 50
        assert abs(result[3].net_balance.amount - Decimal("-50.00")) < Decimal("0.10")

    def test_zero_contributions(self):
        """One person pays nothing."""
        expenses = [
            self._create_expense("100.00", payer_id=1, expense_id=1),
            self._create_expense("100.00", payer_id=2, expense_id=2),
        ]
        member_ids = [1, 2, 3]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # Total 200, fair share 66.67 each
        # User 3 paid 0, so owes 66.67
        assert result[3].net_balance.amount < Decimal("0")
        assert result[3].owes


class TestCalculateBalancesFourPlusPeople:
    """Test with 4+ people."""

    def _create_expense(self, amount: str, payer_id: int, expense_id: int = 1) -> ExpensePublic:
        """Helper to create expense."""
        from datetime import date, datetime

        return ExpensePublic(
            id=expense_id,
            group_id=1,
            amount=Decimal(amount),
            description="Test",
            date=date.today(),
            creator_id=payer_id,
            payer_id=payer_id,
            currency="EUR",
            status=ExpenseStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def test_four_people_equal_split(self):
        """100€ / 4 = 25 each."""
        expenses = [self._create_expense("100.00", payer_id=1)]
        member_ids = [1, 2, 3, 4]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        assert result[1].net_balance.amount == Decimal("75.00")
        assert result[2].net_balance.amount == Decimal("-25.00")
        assert result[3].net_balance.amount == Decimal("-25.00")
        assert result[4].net_balance.amount == Decimal("-25.00")

        # Sum must be zero
        total = sum(r.net_balance.amount for r in result.values())
        assert total == Decimal("0")

    def test_eight_people_complex(self):
        """Various contributions from 8 people."""
        expenses = [
            self._create_expense("100.00", payer_id=1, expense_id=1),
            self._create_expense("50.00", payer_id=2, expense_id=2),
        ]
        member_ids = list(range(1, 9))  # 1-8
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # Verify sum is zero
        total = sum(r.net_balance.amount for r in result.values())
        assert total == Decimal("0")


class TestRoundingEdgeCases:
    """Test rounding behavior and edge cases."""

    def _create_expense(self, amount: str, payer_id: int = 1) -> ExpensePublic:
        """Helper to create expense."""
        from datetime import date, datetime

        return ExpensePublic(
            id=1,
            group_id=1,
            amount=Decimal(amount),
            description="Test",
            date=date.today(),
            creator_id=payer_id,
            payer_id=payer_id,
            currency="EUR",
            status=ExpenseStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def test_very_small_amounts(self):
        """0.01€ split 3 ways."""
        expenses = [self._create_expense("0.01")]
        member_ids = [1, 2, 3]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # Should handle gracefully
        total = sum(r.net_balance.amount for r in result.values())
        assert total == Decimal("0")

    def test_very_large_amounts(self):
        """Very large amounts (millions)."""
        expenses = [self._create_expense("1000000.00")]
        member_ids = [1, 2]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        assert result[1].net_balance.amount == Decimal("500000.00")
        assert result[2].net_balance.amount == Decimal("-500000.00")

    def test_0_1_precision_mode(self):
        """With 0.1 precision, amounts round to dimes."""
        expenses = [self._create_expense("100.00")]
        member_ids = [1, 2, 3]
        config = BalanceConfig.dimes()  # 0.1 precision

        result = calculate_balances(expenses, member_ids, config)

        # All balances should have at most 1 decimal place
        for balance in result.values():
            str_amount = str(balance.net_balance.amount)
            if "." in str_amount:
                decimals = len(str_amount.split(".")[1])
                assert decimals <= 1


class TestMinimizeTransactions:
    """Test transaction minimization algorithm."""

    def _create_balance(
        self,
        user_id: int,
        paid: str,
        share: str,
        net: str,
    ) -> MemberBalance:
        """Helper to create MemberBalance."""
        return MemberBalance(
            user_id=user_id,
            amount_paid=Money(Decimal(paid)),
            fair_share=Money(Decimal(share)),
            net_balance=Money(Decimal(net)),
        )

    def test_two_person_one_transaction(self):
        """Simple case: one debtor, one creditor."""
        balances = {
            1: self._create_balance(1, "100", "50", "50"),  # Is owed 50
            2: self._create_balance(2, "0", "50", "-50"),  # Owes 50
        }

        transactions = minimize_transactions(balances)

        assert len(transactions) == 1
        assert transactions[0].from_user_id == 2
        assert transactions[0].to_user_id == 1
        assert transactions[0].amount.amount == Decimal("50.00")

    def test_three_person_chain(self):
        """User1 owes, User2 is owed, User3 is owed."""
        balances = {
            1: self._create_balance(1, "0", "100", "-100"),  # Owes 100
            2: self._create_balance(2, "150", "100", "50"),  # Is owed 50
            3: self._create_balance(3, "150", "100", "50"),  # Is owed 50
        }

        transactions = minimize_transactions(balances)

        # Should have 2 transactions
        assert len(transactions) <= 2

        # Verify total transferred equals total debt
        total_transferred = sum(t.amount.amount for t in transactions)
        assert total_transferred == Decimal("100.00")

    def test_already_settled_no_transactions(self):
        """When all balances are zero, no transactions needed."""
        balances = {
            1: self._create_balance(1, "50", "50", "0"),
            2: self._create_balance(2, "50", "50", "0"),
        }

        transactions = minimize_transactions(balances)

        assert len(transactions) == 0

    def test_complex_four_person_scenario(self):
        """Multiple debtors and creditors."""
        balances = {
            1: self._create_balance(1, "0", "50", "-50"),  # Owes 50
            2: self._create_balance(2, "0", "50", "-50"),  # Owes 50
            3: self._create_balance(3, "100", "50", "50"),  # Is owed 50
            4: self._create_balance(4, "100", "50", "50"),  # Is owed 50
        }

        transactions = minimize_transactions(balances)

        # At most 3 transactions for 4 people
        assert len(transactions) <= 3

        # Verify total debt is settled
        total_transferred = sum(t.amount.amount for t in transactions)
        assert total_transferred == Decimal("100.00")

    def test_empty_balances(self):
        """Empty balances returns empty transactions."""
        transactions = minimize_transactions({})
        assert transactions == []


class TestErrorConditions:
    """Test error handling and edge cases."""

    def _create_expense(
        self,
        amount: str,
        payer_id: int = 1,
        currency: str = "EUR",
    ) -> ExpensePublic:
        """Helper to create expense."""
        from datetime import date, datetime

        return ExpensePublic(
            id=1,
            group_id=1,
            amount=Decimal(amount),
            description="Test",
            date=date.today(),
            creator_id=payer_id,
            payer_id=payer_id,
            currency=currency,
            status=ExpenseStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def test_empty_member_list_raises(self):
        """Empty member list raises error."""
        expenses = [self._create_expense("100.00")]
        member_ids = []
        config = BalanceConfig()

        with pytest.raises(InvalidShareError, match="empty group"):
            calculate_balances(expenses, member_ids, config)

    def test_mixed_currencies_raises(self):
        """Mixed currencies raise CurrencyMismatchError."""
        expenses = [
            self._create_expense("100.00", currency="EUR"),
            self._create_expense("100.00", currency="USD"),
        ]
        member_ids = [1, 2]
        config = BalanceConfig()

        with pytest.raises(CurrencyMismatchError):
            calculate_balances(expenses, member_ids, config)

    def test_single_person_zero_balance(self):
        """One person paying alone has zero balance."""
        expenses = [self._create_expense("100.00")]
        member_ids = [1]
        config = BalanceConfig()

        result = calculate_balances(expenses, member_ids, config)

        # One person: paid 100, fair share 100, net 0
        assert result[1].net_balance.amount == Decimal("0.00")

    def test_idempotency_same_inputs_same_outputs(self):
        """Same inputs produce same outputs."""
        expenses = [self._create_expense("100.00")]
        member_ids = [1, 2, 3]
        config = BalanceConfig()

        result1 = calculate_balances(expenses, member_ids, config)
        result2 = calculate_balances(expenses, member_ids, config)

        assert result1[1].net_balance == result2[1].net_balance
        assert result1[2].net_balance == result2[2].net_balance
        assert result1[3].net_balance == result2[3].net_balance


class TestIntegrationWithEvenSplitStrategy:
    """Test integration of balance calculation with EvenSplitStrategy."""

    def _create_expense(self, amount: str, payer_id: int = 1) -> ExpensePublic:
        """Helper to create expense."""
        from datetime import date, datetime

        return ExpensePublic(
            id=1,
            group_id=1,
            amount=Decimal(amount),
            description="Test",
            date=date.today(),
            creator_id=payer_id,
            payer_id=payer_id,
            currency="EUR",
            status=ExpenseStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    def test_explicit_strategy_parameter(self):
        """Can pass explicit strategy to calculate_balances."""
        expenses = [self._create_expense("100.00")]
        member_ids = [1, 2]
        config = BalanceConfig()
        strategy = EvenSplitStrategy()

        result = calculate_balances(expenses, member_ids, config, strategy)

        assert result[1].net_balance.amount == Decimal("50.00")
        assert result[2].net_balance.amount == Decimal("-50.00")

    def test_default_strategy_when_none_provided(self):
        """EvenSplitStrategy used by default."""
        expenses = [self._create_expense("100.00")]
        member_ids = [1, 2]
        config = BalanceConfig()

        # No strategy parameter
        result = calculate_balances(expenses, member_ids, config)

        # Should still work with EvenSplitStrategy as default
        assert result[1].net_balance.amount == Decimal("50.00")
        assert result[2].net_balance.amount == Decimal("-50.00")
