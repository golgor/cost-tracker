"""Configuration for balance calculations."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BalanceConfig:
    """Configuration for balance calculations.

    Immutable configuration object that controls rounding behavior.

    Attributes:
        rounding_precision: Decimal precision for rounding (default: 0.01 = cents)
        rounding_mode: Rounding mode string (default: "ROUND_HALF_EVEN")

    Example:
        >>> config = BalanceConfig()
        >>> config.rounding_precision
        Decimal('0.01')

        >>> config_dimes = BalanceConfig(rounding_precision=Decimal("0.1"))
    """

    rounding_precision: Decimal = Decimal("0.01")
    rounding_mode: str = "ROUND_HALF_EVEN"

    def __post_init__(self):
        """Validate configuration."""
        # Validate precision is positive
        if self.rounding_precision <= 0:
            raise ValueError(f"Rounding precision must be positive, got {self.rounding_precision}")

        # Validate precision is a power of 10 (0.1, 0.01, 0.001, etc.)
        str_val = str(self.rounding_precision)
        if "." in str_val:
            decimals = len(str_val.split(".")[1].rstrip("0"))
            expected = Decimal("0.1") ** decimals if decimals > 0 else Decimal("1")
        else:
            expected = Decimal("1")

        if self.rounding_precision != expected:
            raise ValueError(
                f"Rounding precision must be a power of 10, got {self.rounding_precision}. "
                f"Expected: {expected}"
            )

        # Validate rounding mode
        valid_modes = ["ROUND_HALF_EVEN", "ROUND_HALF_UP", "ROUND_DOWN"]
        if self.rounding_mode not in valid_modes:
            raise ValueError(
                f"Invalid rounding mode: {self.rounding_mode}. Must be one of: {valid_modes}"
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
