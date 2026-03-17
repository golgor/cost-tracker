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


class UserAlreadyDeactivated(DomainError):
    """Raised when attempting to deactivate an already deactivated user."""


class UserAlreadyActive(DomainError):
    """Raised when attempting to activate an already active user."""
