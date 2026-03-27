"""Tests for normalized_monthly_cost() pure domain function."""

from decimal import Decimal

import pytest

from app.domain.models import RecurringFrequency
from app.domain.recurring import normalized_monthly_cost


class TestNormalizedMonthlyCost:
    """Unit tests for normalized_monthly_cost()."""

    def test_monthly_returns_amount_unchanged(self):
        """MONTHLY frequency: normalized cost equals the original amount."""
        result = normalized_monthly_cost(Decimal("14.99"), RecurringFrequency.MONTHLY)
        assert result == Decimal("14.99")

    def test_quarterly_divides_by_three(self):
        """QUARTERLY frequency: normalized cost is amount / 3."""
        result = normalized_monthly_cost(Decimal("90.00"), RecurringFrequency.QUARTERLY)
        assert result == Decimal("30.00")

    def test_semi_annually_divides_by_six(self):
        """SEMI_ANNUALLY frequency: normalized cost is amount / 6."""
        result = normalized_monthly_cost(Decimal("340.00"), RecurringFrequency.SEMI_ANNUALLY)
        assert result == Decimal("56.67")  # 340/6 = 56.666... → rounds to 56.67

    def test_yearly_divides_by_twelve(self):
        """YEARLY frequency: normalized cost is amount / 12."""
        result = normalized_monthly_cost(Decimal("1200.00"), RecurringFrequency.YEARLY)
        assert result == Decimal("100.00")

    def test_every_n_months_divides_by_interval(self):
        """EVERY_N_MONTHS: normalized cost is amount / interval_months."""
        result = normalized_monthly_cost(
            Decimal("340.00"),
            RecurringFrequency.EVERY_N_MONTHS,
            interval_months=6,
        )
        assert result == Decimal("56.67")

    def test_every_n_months_with_2_months(self):
        """EVERY_N_MONTHS with 2 months: normalized cost is amount / 2."""
        result = normalized_monthly_cost(
            Decimal("50.00"),
            RecurringFrequency.EVERY_N_MONTHS,
            interval_months=2,
        )
        assert result == Decimal("25.00")

    def test_result_is_decimal(self):
        """Result is always a Decimal instance."""
        result = normalized_monthly_cost(Decimal("14.99"), RecurringFrequency.MONTHLY)
        assert isinstance(result, Decimal)

    def test_result_rounds_half_up(self):
        """Result uses ROUND_HALF_UP (not banker's rounding)."""
        # 10 / 3 = 3.3333... → 3.33
        result = normalized_monthly_cost(Decimal("10.00"), RecurringFrequency.QUARTERLY)
        assert result == Decimal("3.33")

        # 11 / 3 = 3.6666... → 3.67
        result2 = normalized_monthly_cost(Decimal("11.00"), RecurringFrequency.QUARTERLY)
        assert result2 == Decimal("3.67")

    def test_every_n_months_raises_without_interval(self):
        """EVERY_N_MONTHS without interval_months raises ValueError."""
        with pytest.raises(ValueError, match="interval_months must be"):
            normalized_monthly_cost(Decimal("100.00"), RecurringFrequency.EVERY_N_MONTHS)

    def test_every_n_months_raises_with_zero_interval(self):
        """EVERY_N_MONTHS with interval_months=0 raises ValueError."""
        with pytest.raises(ValueError):
            normalized_monthly_cost(
                Decimal("100.00"),
                RecurringFrequency.EVERY_N_MONTHS,
                interval_months=0,
            )

    def test_result_has_two_decimal_places(self):
        """Result is always quantized to 2 decimal places."""
        result = normalized_monthly_cost(Decimal("14.99"), RecurringFrequency.MONTHLY)
        # Decimal("14.99") has 2 decimal places from quantize
        assert result == Decimal("14.99")
        assert str(result) == "14.99"

    def test_yearly_odd_amount(self):
        """YEARLY with amount that doesn't divide evenly rounds correctly."""
        # 100 / 12 = 8.333... → 8.33
        result = normalized_monthly_cost(Decimal("100.00"), RecurringFrequency.YEARLY)
        assert result == Decimal("8.33")

    def test_every_n_months_large_interval(self):
        """EVERY_N_MONTHS with large interval (e.g. 24 = bi-yearly) works correctly."""
        result = normalized_monthly_cost(
            Decimal("2400.00"),
            RecurringFrequency.EVERY_N_MONTHS,
            interval_months=24,
        )
        assert result == Decimal("100.00")
