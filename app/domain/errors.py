class DomainError(Exception):
    """Base class for all domain errors."""


class DuplicateHouseholdError(DomainError):
    """Raised when user already belongs to a household."""
