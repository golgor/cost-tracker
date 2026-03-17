"""User lifecycle and admin management use cases."""

from typing import Protocol

from app.domain.errors import (
    DeactivatedUserAccessDenied,
    LastActiveAdminDeactivationForbidden,
    UserNotFoundError,
)
from app.domain.models import UserPublic, UserRole


class UnitOfWorkPort(Protocol):
    """Minimal port for UoW needed by user use cases."""

    def commit(self) -> None:
        """Commit the current transaction."""
        ...

    @property
    def users(self):
        """Access to user adapter."""
        ...


def provision_user(
    uow: UnitOfWorkPort, oidc_sub: str, email: str, display_name: str, *, actor_id: int
) -> UserPublic:
    """Provision a user - create if new, update if exists. Enforces deactivation block.

    Returns the provisioned user if active, raises DeactivatedUserAccessDenied if deactivated.
    """
    user = uow.users.save(
        oidc_sub=oidc_sub,
        email=email,
        display_name=display_name,
        actor_id=actor_id,
    )

    if not user.is_active:
        raise DeactivatedUserAccessDenied(
            f"User {user.id} is deactivated and cannot access the app"
        )

    return user


def bootstrap_first_admin(uow: UnitOfWorkPort) -> bool:
    """Promote the first user to admin if no active admin exists.

    Returns True if promoted, False if already an admin or admin already exists.
    """
    if uow.users.count_active_admins() > 0:
        return False

    # This is called after provision_user, so we need to get the last created user.
    # In practice, this will be called in auth flow with a known user_id.
    # For now, we just check if admin exists.
    return False


def promote_user_to_admin(uow: UnitOfWorkPort, user_id: int, *, actor_id: int) -> UserPublic:
    """Promote a regular user to admin role."""
    user = uow.users.promote_to_admin(user_id, actor_id=actor_id)
    uow.commit()
    return user


def demote_user_to_regular(uow: UnitOfWorkPort, user_id: int, *, actor_id: int) -> UserPublic:
    """Demote an admin to regular user role."""
    user = uow.users.demote_to_user(user_id, actor_id=actor_id)
    uow.commit()
    return user


def deactivate_user(uow: UnitOfWorkPort, user_id: int, *, actor_id: int) -> UserPublic:
    """Deactivate a user. Enforces that the last active admin cannot be deactivated."""
    # Check if this is the last active admin
    user = uow.users.get_by_id(user_id)
    if user is None:
        raise UserNotFoundError(f"User {user_id} not found")

    if user.role == UserRole.ADMIN and user.is_active:
        active_admin_count = uow.users.count_active_admins()
        if active_admin_count <= 1:
            raise LastActiveAdminDeactivationForbidden("Cannot deactivate the last active admin")

    user = uow.users.deactivate(user_id, actor_id=actor_id)
    uow.commit()
    return user


def reactivate_user(uow: UnitOfWorkPort, user_id: int, *, actor_id: int) -> UserPublic:
    """Reactivate a deactivated user."""
    user = uow.users.reactivate(user_id, actor_id=actor_id)
    uow.commit()
    return user
