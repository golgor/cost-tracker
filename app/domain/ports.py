# Domain ports (Protocol classes)
# Allowed imports: stdlib + external validation libs (sqlmodel, pydantic) per ADR-011
# Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
from typing import Protocol

from app.domain.models import UserPublic


class UserPort(Protocol):
    """Port for User persistence operations."""

    def get_by_id(self, user_id: int) -> UserPublic | None:
        """Retrieve user by database ID."""
        ...

    def get_by_oidc_sub(self, oidc_sub: str) -> UserPublic | None:
        """Retrieve user by OIDC subject identifier."""
        ...

    def save(self, oidc_sub: str, email: str, display_name: str) -> UserPublic:
        """Create or update a user. Returns the persisted user."""
        ...
