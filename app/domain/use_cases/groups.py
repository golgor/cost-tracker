import logging

from app.domain.errors import DomainError
from app.domain.models import GroupPublic, MemberRole, MembershipPublic, SplitType

logger = logging.getLogger(__name__)


class DuplicateHouseholdError(DomainError):
    """Raised when user already belongs to a household."""


def create_household(
    uow,
    user_id: int,
    name: str,
    default_currency: str = "EUR",
    default_split_type: SplitType = SplitType.EVEN,
) -> GroupPublic:
    """
    Create household with current user as first admin.

    Handles race condition: if another user created a group while
    this user was in the wizard, check if we should join as regular user.
    """
    existing = uow.groups.get_by_user_id(user_id)
    if existing:
        raise DuplicateHouseholdError("User already belongs to a household")

    if uow.groups.has_active_admin():
        group = uow.groups.get_default_group()
        if group:
            uow.groups.add_member(group.id, user_id, MemberRole.USER)
            uow.commit()
            logger.info(
                "User %d joined existing group %d as USER (race condition)",
                user_id,
                group.id,
            )
            return group
        raise DuplicateHouseholdError("Active admin exists but no group found")

    group = uow.groups.save(
        name=name,
        default_currency=default_currency,
        default_split_type=default_split_type,
    )
    uow.groups.add_member(group.id, user_id, MemberRole.ADMIN)
    uow.commit()

    logger.info(
        "User %d created household '%s' (group %d) as ADMIN",
        user_id,
        name,
        group.id,
    )

    return group


def add_member(
    uow,
    group_id: int,
    user_id: int,
    role: MemberRole = MemberRole.USER,
) -> MembershipPublic:
    """Add a user to a group with specified role."""
    existing = uow.groups.get_membership(user_id, group_id)
    if existing:
        raise DuplicateHouseholdError("User is already a member of this group")

    membership = uow.groups.add_member(group_id, user_id, role)
    uow.commit()

    logger.info(
        "User %d added to group %d with role %s",
        user_id,
        group_id,
        role.value,
    )

    return membership


def get_user_group(uow, user_id: int) -> GroupPublic | None:
    """Get the group that a user belongs to."""
    return uow.groups.get_by_user_id(user_id)


def has_active_admin(uow) -> bool:
    """Check if any active admin exists in the system."""
    return uow.groups.has_active_admin()
