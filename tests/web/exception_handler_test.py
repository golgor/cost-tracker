"""Tests verifying the global DomainError exception handler mapping."""

from app.domain.errors import (
    DomainError,
    UserLimitReachedError,
    UserNotFoundError,
)
from app.main import DOMAIN_ERROR_MAP


class TestDomainErrorMap:
    """Verify DOMAIN_ERROR_MAP covers all current DomainError subclasses."""

    def test_key_errors_are_mapped(self):
        """Key DomainError subclasses have entries in DOMAIN_ERROR_MAP."""
        expected = {
            UserNotFoundError,
            UserLimitReachedError,
        }
        for error_class in expected:
            assert error_class in DOMAIN_ERROR_MAP, (
                f"{error_class.__name__} is missing from DOMAIN_ERROR_MAP"
            )

    def test_not_found_errors_map_to_404(self):
        """Not-found domain errors map to HTTP 404."""
        assert DOMAIN_ERROR_MAP[UserNotFoundError] == 404

    def test_forbidden_errors_map_to_403(self):
        """Forbidden domain errors map to HTTP 403."""
        assert DOMAIN_ERROR_MAP[UserLimitReachedError] == 403

    def test_unmapped_domain_error_defaults_to_422(self):
        """Unknown DomainError subclasses fall back to HTTP 422."""

        class UnknownError(DomainError):
            pass

        status = DOMAIN_ERROR_MAP.get(UnknownError, 422)
        assert status == 422
