"""User lifecycle and admin management use cases."""

from app.domain.errors import (
    DeactivatedUserAccessDenied,
    LastActiveAdminDeactivationForbidden,
    UserNotFoundError,
)
from app.domain.models import UserPublic, UserRole
from app.domain.ports import UnitOfWorkPort


def provision_user(
    uow: UnitOfWorkPort, oidc_sub: str, email: str, display_name: str, *, actor_id: int
) -> UserPublic:
    """Provision a user - create if new, update if exists. Enforces deactivation block.

    Returns the provisioned user if active, raises DeactivatedUserAccessDenied if deactivated.
    Transaction must be committed by caller using `with uow:`.
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


def bootstrap_first_admin(
    uow: UnitOfWorkPort, user_id: int, *, actor_id: int
) -> tuple[UserPublic, bool]:
    """Promote the first user to admin if no active admin exists.

    Returns tuple of (user, was_promoted) where was_promoted is True if this user
    was promoted to admin as the first admin.

    Transaction must be committed by caller using `with uow:`.
    """
    if uow.users.count_active_admins() > 0:
        user = uow.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")
        return user, False

    # First user - promote to admin
    user = uow.users.promote_to_admin(user_id, actor_id=actor_id)
    return user, True


def promote_user_to_admin(uow: UnitOfWorkPort, user_id: int, *, actor_id: int) -> UserPublic:
    """Promote a regular user to admin role.

    Transaction must be committed by caller using `with uow:`.
    """
    user = uow.users.promote_to_admin(user_id, actor_id=actor_id)
    return user


def demote_user_to_regular(uow: UnitOfWorkPort, user_id: int, *, actor_id: int) -> UserPublic:
    """Demote an admin to regular user role.

    Transaction must be committed by caller using `with uow:`.
    """
    user = uow.users.demote_to_user(user_id, actor_id=actor_id)
    return user


def deactivate_user(uow: UnitOfWorkPort, user_id: int, *, actor_id: int) -> UserPublic:
    """Deactivate a user. Enforces that the last active admin cannot be deactivated.

    Transaction must be committed by caller using `with uow:`.
    """
    # Check if this is the last active admin
    user = uow.users.get_by_id(user_id)
    if user is None:
        raise UserNotFoundError(f"User {user_id} not found")

    if user.role == UserRole.ADMIN and user.is_active:
        active_admin_count = uow.users.count_active_admins()
        if active_admin_count <= 1:
            raise LastActiveAdminDeactivationForbidden("Cannot deactivate the last active admin")

    user = uow.users.deactivate(user_id, actor_id=actor_id)
    return user


def reactivate_user(uow: UnitOfWorkPort, user_id: int, *, actor_id: int) -> UserPublic:
    """Reactivate a deactivated user.

    Transaction must be committed by caller using `with uow:`.
    """
    user = uow.users.reactivate(user_id, actor_id=actor_id)
    return user
