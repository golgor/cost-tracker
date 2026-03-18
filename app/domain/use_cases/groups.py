from app.domain.errors import (
    DuplicateHouseholdError,
    DuplicateMembershipError,
    GroupNotFoundError,
    UnauthorizedGroupActionError,
)
from app.domain.models import GroupPublic, MemberRole, MembershipPublic, SplitType
from app.domain.ports import UnitOfWorkPort


def create_household(
    uow: UnitOfWorkPort,
    user_id: int,
    name: str,
    default_currency: str = "EUR",
    default_split_type: SplitType = SplitType.EVEN,
    tracking_threshold: int = 30,
) -> GroupPublic:
    """Create household with current user as first admin.

    Handles race condition: if another user created a group while
    this user was in the wizard, check if we should join as regular user.

    Transaction must be committed by caller using `with uow:`.
    """
    existing = uow.groups.get_by_user_id(user_id)
    if existing:
        raise DuplicateHouseholdError("User already belongs to a household")

    if uow.groups.has_active_admin():
        group = uow.groups.get_default_group()
        if group is None:
            raise GroupNotFoundError("Active admin exists but no default group found")

        try:
            uow.groups.add_member(
                group.id,
                user_id,
                MemberRole.USER,
                actor_id=user_id,
            )
        except DuplicateMembershipError:
            # Idempotent for concurrent first-login callbacks.
            pass

        return group

    group = uow.groups.save(
        name,
        actor_id=user_id,
        default_currency=default_currency,
        default_split_type=default_split_type,
        tracking_threshold=tracking_threshold,
    )
    uow.groups.add_member(group.id, user_id, MemberRole.ADMIN, actor_id=user_id)

    return group


def add_member(
    uow: UnitOfWorkPort,
    group_id: int,
    user_id: int,
    role: MemberRole = MemberRole.USER,
) -> MembershipPublic:
    """Add a user to a group with specified role.

    Transaction must be committed by caller using `with uow:`.
    """
    group = uow.groups.get_by_id(group_id)
    if group is None:
        raise GroupNotFoundError(f"Group {group_id} not found")

    existing = uow.groups.get_membership(user_id, group_id)
    if existing:
        raise DuplicateMembershipError("User is already a member of this group")

    membership = uow.groups.add_member(
        group_id,
        user_id,
        role,
        actor_id=user_id,
    )

    return membership


def get_user_group(uow: UnitOfWorkPort, user_id: int) -> GroupPublic | None:
    """Get the group that a user belongs to."""
    return uow.groups.get_by_user_id(user_id)


def has_active_admin(uow: UnitOfWorkPort) -> bool:
    """Check if any active admin exists in the system."""
    return uow.groups.has_active_admin()


def update_group_defaults(
    uow: UnitOfWorkPort,
    *,
    actor_user_id: int,
    group_id: int,
    default_currency: str | None = None,
    default_split_type: SplitType | None = None,
    tracking_threshold: int | None = None,
) -> GroupPublic:
    """Update group defaults, restricted to admin members of the group.

    Transaction must be committed by caller using `with uow:`.
    """
    role = uow.groups.get_member_role(actor_user_id, group_id)
    if role != MemberRole.ADMIN:
        raise UnauthorizedGroupActionError("Only admins can update group defaults")

    updated_group = uow.groups.update(
        group_id,
        actor_id=actor_user_id,
        default_currency=default_currency,
        default_split_type=default_split_type,
        tracking_threshold=tracking_threshold,
    )
    return updated_group
