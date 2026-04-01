class DomainError(Exception):
    """Base class for all domain errors."""


class UserNotFoundError(DomainError):
    """Raised when a user cannot be found."""


class UserLimitReachedError(DomainError):
    """Raised when the maximum number of users has been reached."""


class CannotEditSettledExpenseError(DomainError):
    """Raised when attempting to edit a settled expense (immutable)."""

    def __init__(self, expense_id: int):
        super().__init__(f"Cannot edit expense {expense_id}: expense is settled and immutable")
        self.expense_id = expense_id


class SettlementError(DomainError):
    """Base error for settlement operations."""


class EmptySettlementError(SettlementError):
    """Raised when attempting to settle with no expenses."""

    def __init__(self) -> None:
        super().__init__("Please select at least one expense to settle")


class StaleExpenseError(SettlementError):
    """Raised when a selected expense is already settled."""

    def __init__(self, expense_id: int) -> None:
        super().__init__(f"Expense {expense_id} has already been settled")
        self.expense_id = expense_id


class BalanceCalculationError(DomainError):
    """Base error for balance calculation failures."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidShareError(BalanceCalculationError):
    """Raised when share calculation fails.

    Examples:
        - Empty member list
        - Invalid share percentages (don't sum to 100)
        - Negative shares
    """

    def __init__(self, message: str):
        super().__init__(message)


class RoundingPrecisionError(BalanceCalculationError):
    """Raised when rounding configuration is invalid.

    Examples:
        - Precision is not a power of 10 (e.g., 0.05 instead of 0.01)
        - Precision is negative or zero
        - Invalid rounding mode
    """

    def __init__(self, precision: str):
        super().__init__(f"Invalid rounding precision: {precision}")
        self.precision = precision


class CurrencyMismatchError(BalanceCalculationError):
    """Raised when expenses have different currencies.

    Balance calculation currently requires all expenses to be in the same currency.
    """

    def __init__(self, currencies: set[str]):
        currency_list = ", ".join(sorted(currencies))
        super().__init__(f"Cannot calculate balances with mixed currencies: {currency_list}")
        self.currencies = currencies


class RecurringDefinitionNotFoundError(DomainError):
    """Raised when a recurring definition cannot be found or is soft-deleted."""


class DuplicateBillingPeriodError(DomainError):
    """Raised when an expense for this billing period already exists."""

    def __init__(self, definition_id: int, billing_period: str):
        super().__init__(
            f"An expense for definition {definition_id} in period {billing_period} already exists"
        )
        self.definition_id = definition_id
        self.billing_period = billing_period


class RecurringExpenseDescriptionError(DomainError):
    """Raised when attempting to change the description of a recurring expense."""


class ExpenseNotFoundError(DomainError):
    """Raised when an expense cannot be found."""

    def __init__(self, expense_id: int):
        super().__init__(f"Expense {expense_id} not found")
        self.expense_id = expense_id


class TripNotFoundError(DomainError):
    """Raised when a trip cannot be found."""

    def __init__(self, trip_id: int):
        super().__init__(f"Trip {trip_id} not found")
        self.trip_id = trip_id


class TripNotActiveError(DomainError):
    """Raised when attempting to modify a settled/closed trip."""

    def __init__(self, trip_id: int):
        super().__init__(f"Trip {trip_id} is settled and cannot be modified")
        self.trip_id = trip_id


class TripExpenseNotFoundError(DomainError):
    """Raised when a trip expense cannot be found."""

    def __init__(self, expense_id: int):
        super().__init__(f"Trip expense {expense_id} not found")
        self.expense_id = expense_id


class TripAuthorizationError(DomainError):
    """Raised when user is not authorized to manage a trip."""

    def __init__(self) -> None:
        super().__init__("Not authorized to manage this trip")


# Centralised mapping from domain errors to HTTP status codes.
# Used by both the web app (main.py) and the API sub-app (router.py).
HTTP_STATUS_MAP: dict[type[DomainError], int] = {
    UserNotFoundError: 404,
    UserLimitReachedError: 403,
    CannotEditSettledExpenseError: 403,
    EmptySettlementError: 400,
    StaleExpenseError: 409,
    RecurringDefinitionNotFoundError: 404,
    DuplicateBillingPeriodError: 409,
    RecurringExpenseDescriptionError: 400,
    ExpenseNotFoundError: 404,
    TripNotFoundError: 404,
    TripNotActiveError: 403,
    TripExpenseNotFoundError: 404,
    TripAuthorizationError: 403,
}
