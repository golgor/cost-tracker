"""Configuration for balance calculations."""

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

VALID_ROUNDING_MODES = {ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_DOWN}


@dataclass(frozen=True)
class BalanceConfig:
    """Configuration for balance calculations.

    Immutable configuration object that controls rounding behavior.

    Attributes:
        rounding_precision: Decimal precision for rounding (default: 0.01 = cents)
        rounding_mode: Rounding mode constant (default: ROUND_HALF_EVEN)

    Example:
        >>> config = BalanceConfig()
        >>> config.rounding_precision
        Decimal('0.01')

        >>> config_dimes = BalanceConfig(rounding_precision=Decimal("0.1"))
    """

    rounding_precision: Decimal = Decimal("0.01")
    rounding_mode: str = ROUND_HALF_EVEN  # type: ignore[assignment]

    def __post_init__(self):
        """Validate configuration."""
        if self.rounding_precision <= 0:
            raise ValueError(f"Rounding precision must be positive, got {self.rounding_precision}")

        # Require precision to be 1 or a fractional power of 10 (0.1, 0.01, 0.001, ...)
        value = self.rounding_precision
        while value < 1:
            value *= 10
        if value != 1:
            raise ValueError(
                f"Rounding precision must be a power of 10, got {self.rounding_precision}"
            )

        if self.rounding_mode not in VALID_ROUNDING_MODES:
            raise ValueError(
                f"Invalid rounding mode: {self.rounding_mode}. "
                f"Must be one of: {sorted(VALID_ROUNDING_MODES)}"
            )

    @classmethod
    def default(cls) -> BalanceConfig:
        """Get default configuration (cents precision, banker's rounding).

        Returns:
            Default BalanceConfig instance
        """
        return cls()

    @classmethod
    def dimes(cls) -> BalanceConfig:
        """Get configuration with dimes precision (0.1).

        Returns:
            BalanceConfig with 0.1 precision
        """
        return cls(rounding_precision=Decimal("0.1"))
