"""User lifecycle use cases."""

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
