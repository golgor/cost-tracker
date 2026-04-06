"""Value objects for the domain layer.

Immutable objects that represent values with no identity.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class Money:
    """Immutable value object representing monetary amounts.

    Provides type-safe arithmetic operations with currency validation.
    All operations preserve the currency and handle rounding appropriately.

    Example:
        >>> m1 = Money(Decimal("100.00"), "EUR")
        >>> m2 = Money(Decimal("50.00"), "EUR")
        >>> m1 + m2
        Money(amount=Decimal('150.00'), currency='EUR')
    """

    amount: Decimal
    currency: str = "EUR"

    def __post_init__(self):
        """Validate and normalize the amount."""
        # Convert to Decimal if string or int
        try:
            decimal_amount = Decimal(str(self.amount))
        except InvalidOperation as e:
            raise ValueError(f"Invalid amount: {self.amount}") from e

        # Check for NaN or Infinity
        if decimal_amount.is_nan():
            raise ValueError(f"Amount cannot be NaN: {decimal_amount}")
        if decimal_amount.is_infinite():
            raise ValueError(f"Amount cannot be infinite: {decimal_amount}")

        # Use object.__setattr__ because dataclass is frozen
        object.__setattr__(self, "amount", decimal_amount)

    def __add__(self, other: Money) -> Money:
        """Add two Money amounts.

        Args:
            other: Money to add

        Returns:
            New Money with sum

        Raises:
            ValueError: If currencies don't match
        """
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        """Subtract one Money from another.

        Args:
            other: Money to subtract

        Returns:
            New Money with difference

        Raises:
            ValueError: If currencies don't match
        """
        self._assert_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, multiplier: int | Decimal) -> Money:
        """Multiply Money by a scalar.

        Args:
            multiplier: Integer or Decimal multiplier

        Returns:
            New Money with multiplied amount
        """
        if isinstance(multiplier, int):
            multiplier = Decimal(multiplier)
        result = self.amount * multiplier
        return Money(result, self.currency)

    def __truediv__(self, divisor: int | Decimal) -> Money:
        """Divide Money by a scalar.

        Args:
            divisor: Integer or Decimal divisor

        Returns:
            New Money with divided amount

        Raises:
            ValueError: If divisor is zero
        """
        if isinstance(divisor, int):
            divisor = Decimal(divisor)
        if divisor == 0:
            raise ValueError("Cannot divide by zero")
        result = self.amount / divisor
        return Money(result, self.currency)

    def __eq__(self, other: object) -> bool:
        """Check equality with another Money."""
        if not isinstance(other, Money):
            return NotImplemented
        return self.amount == other.amount and self.currency == other.currency

    def __hash__(self) -> int:
        """Hash for use in sets and dicts."""
        return hash((self.amount, self.currency))

    def __lt__(self, other: Money) -> bool:
        """Less than comparison."""
        self._assert_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        """Less than or equal comparison."""
        self._assert_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        """Greater than comparison."""
        self._assert_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        """Greater than or equal comparison."""
        self._assert_same_currency(other)
        return self.amount >= other.amount

    def _assert_same_currency(self, other: Money) -> None:
        """Assert that other Money has same currency.

        Args:
            other: Money to compare currency with

        Raises:
            ValueError: If currencies don't match
        """
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch: {self.currency} vs {other.currency}")

    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == 0

    def abs(self) -> Money:
        """Return absolute value."""
        return Money(abs(self.amount), self.currency)
