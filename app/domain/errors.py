class DomainError(Exception):
    """Base class for all domain errors."""


class DuplicateHouseholdError(DomainError):
    """Raised when user already belongs to a household."""


class GroupNotFoundError(DomainError):
    """Raised when a group cannot be found."""


class MembershipNotFoundError(DomainError):
    """Raised when a group membership cannot be found."""


class DuplicateMembershipError(DomainError):
    """Raised when user is already a member of a group."""


class UnauthorizedGroupActionError(DomainError):
    """Raised when user lacks permission for a group-level action."""


class LastActiveAdminDeactivationForbidden(DomainError):
    """Raised when attempting to deactivate the last active admin."""


class UserHasActiveGroupMembershipError(DomainError):
    """Raised when user cannot be deactivated due to active group membership."""


class DeactivatedUserAccessDenied(DomainError):
    """Raised when a deactivated user attempts to access the app."""


class UserNotFoundError(DomainError):
    """Raised when a user cannot be found."""


class UserAlreadyAdminError(DomainError):
    """Raised when attempting to promote a user who is already an admin."""


class UserAlreadyRegularError(DomainError):
    """Raised when attempting to demote a user who is already a regular user."""


class UserAlreadyDeactivated(DomainError):
    """Raised when attempting to deactivate an already deactivated user."""


class CannotEditSettledExpenseError(DomainError):
    """Raised when attempting to edit a settled expense (immutable)."""

    def __init__(self, expense_id: int):
        super().__init__(f"Cannot edit expense {expense_id}: expense is settled and immutable")
        self.expense_id = expense_id


class UserAlreadyActive(DomainError):
    """Raised when attempting to activate an already active user."""


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
