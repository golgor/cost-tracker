"""User lifecycle and admin management use cases."""

from app.domain.errors import UserNotFoundError
from app.domain.models import UserPublic
from app.domain.ports import UnitOfWorkPort


def provision_user(uow: UnitOfWorkPort, oidc_sub: str, email: str, display_name: str) -> UserPublic:
    """Provision a user - create if new, update if exists.

    Transaction must be committed by caller using `with uow:`.
    """
    return uow.users.save(
        oidc_sub=oidc_sub,
        email=email,
        display_name=display_name,
    )


def bootstrap_first_admin(uow: UnitOfWorkPort, user_id: int) -> tuple[UserPublic, bool]:
    """Promote the first user to admin if no admin exists.

    Returns tuple of (user, was_promoted) where was_promoted is True if this user
    was promoted to admin as the first admin.

    Transaction must be committed by caller using `with uow:`.
    """
    if uow.users.count_admins() > 0:
        user = uow.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")
        return user, False

    # First user - promote to admin
    user = uow.users.promote_to_admin(user_id)
    return user, True


def promote_user_to_admin(uow: UnitOfWorkPort, user_id: int) -> UserPublic:
    """Promote a regular user to admin role.

    Transaction must be committed by caller using `with uow:`.
    """
    user = uow.users.promote_to_admin(user_id)
    return user


def demote_user_to_regular(uow: UnitOfWorkPort, user_id: int) -> UserPublic:
    """Demote an admin to regular user role.

    Transaction must be committed by caller using `with uow:`.
    """
    user = uow.users.demote_to_user(user_id)
    return user
