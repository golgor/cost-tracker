# Domain ports (Protocol classes)
# Allowed imports: stdlib + external validation libs (sqlmodel, pydantic) per ADR-011
# Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
from typing import Protocol

from app.domain.models import (
    GroupPublic,
    MemberRole,
    MembershipPublic,
    SplitType,
    UserPublic,
)


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


class GroupPort(Protocol):
    """Port for Group persistence operations."""

    def get_by_id(self, group_id: int) -> GroupPublic | None:
        """Retrieve group by database ID."""
        ...

    def get_by_user_id(self, user_id: int) -> GroupPublic | None:
        """Retrieve group that user belongs to (MVP1: single household)."""
        ...

    def get_default_group(self) -> GroupPublic | None:
        """Get the default/only household group (MVP1: single household)."""
        ...

    def save(
        self,
        name: str,
        default_currency: str = "EUR",
        default_split_type: SplitType = SplitType.EVEN,
    ) -> GroupPublic:
        """Create a new group. Returns the persisted group."""
        ...

    def update(
        self,
        group_id: int,
        name: str | None = None,
        default_currency: str | None = None,
        default_split_type: SplitType | None = None,
    ) -> GroupPublic:
        """Update group configuration. Returns the updated group."""
        ...

    def add_member(self, group_id: int, user_id: int, role: MemberRole) -> MembershipPublic:
        """Add a user to a group with specified role."""
        ...

    def get_membership(self, user_id: int, group_id: int) -> MembershipPublic | None:
        """Get membership for a specific user and group."""
        ...

    def has_active_admin(self) -> bool:
        """Check if any active admin exists in the system (admin bootstrap trigger)."""
        ...
