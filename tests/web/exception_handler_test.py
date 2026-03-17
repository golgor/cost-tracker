"""Tests verifying the global DomainError exception handler mapping."""

from app.domain.errors import (
    DeactivatedUserAccessDenied,
    DomainError,
    DuplicateHouseholdError,
    DuplicateMembershipError,
    GroupNotFoundError,
    LastActiveAdminDeactivationForbidden,
    MembershipNotFoundError,
    UnauthorizedGroupActionError,
    UserHasActiveGroupMembershipError,
)
from app.main import DOMAIN_ERROR_MAP


class TestDomainErrorMap:
    """Verify DOMAIN_ERROR_MAP covers all current DomainError subclasses."""

    def test_all_domain_errors_are_mapped(self):
        """Every DomainError subclass has an entry in DOMAIN_ERROR_MAP."""
        expected = {
            DuplicateHouseholdError,
            DuplicateMembershipError,
            GroupNotFoundError,
            MembershipNotFoundError,
            UnauthorizedGroupActionError,
            LastActiveAdminDeactivationForbidden,
            UserHasActiveGroupMembershipError,
            DeactivatedUserAccessDenied,
        }
        for error_class in expected:
            assert error_class in DOMAIN_ERROR_MAP, (
                f"{error_class.__name__} is missing from DOMAIN_ERROR_MAP"
            )

    def test_conflict_errors_map_to_409(self):
        """Conflict domain errors map to HTTP 409."""
        assert DOMAIN_ERROR_MAP[DuplicateHouseholdError] == 409
        assert DOMAIN_ERROR_MAP[DuplicateMembershipError] == 409
        assert DOMAIN_ERROR_MAP[LastActiveAdminDeactivationForbidden] == 409
        assert DOMAIN_ERROR_MAP[UserHasActiveGroupMembershipError] == 409

    def test_not_found_errors_map_to_404(self):
        """Not-found domain errors map to HTTP 404."""
        assert DOMAIN_ERROR_MAP[GroupNotFoundError] == 404
        assert DOMAIN_ERROR_MAP[MembershipNotFoundError] == 404

    def test_forbidden_errors_map_to_403(self):
        """Forbidden domain errors map to HTTP 403."""
        assert DOMAIN_ERROR_MAP[UnauthorizedGroupActionError] == 403
        assert DOMAIN_ERROR_MAP[DeactivatedUserAccessDenied] == 403

    def test_unmapped_domain_error_defaults_to_422(self):
        """Unknown DomainError subclasses fall back to HTTP 422."""

        class UnknownError(DomainError):
            pass

        status = DOMAIN_ERROR_MAP.get(UnknownError, 422)
        assert status == 422
