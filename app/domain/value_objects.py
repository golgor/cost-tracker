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
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, multiplier: int | Decimal) -> Money:
        return Money(self.amount * multiplier, self.currency)

    def __truediv__(self, divisor: int | Decimal) -> Money:
        if divisor == 0:
            raise ValueError("Cannot divide by zero")
        return Money(self.amount / divisor, self.currency)

    def __lt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount >= other.amount

    def _assert_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValueError(f"Currency mismatch: {self.currency} vs {other.currency}")

    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == 0

    def abs(self) -> Money:
        """Return absolute value."""
        return Money(abs(self.amount), self.currency)
