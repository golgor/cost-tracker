"""View models for template rendering — all display logic lives here.

View models transform domain models into template-ready representations
with pre-computed display strings, CSS classes, and visibility flags.
This keeps templates dumb (no logic) and makes presentation decisions testable.
"""

from pydantic import BaseModel

from app.domain.models import UserPublic, UserRole


class UserRowViewModel(BaseModel):
    """Template-ready representation of a user row in admin table."""

    id: int
    display_name: str
    email: str

    # Pre-computed display strings
    role_label: str
    role_badge_color: str  # Tailwind classes

    # Button visibility flags
    show_promote: bool
    show_demote: bool

    @classmethod
    def from_domain(cls, user: UserPublic, admin_count: int | None = None) -> UserRowViewModel:
        """Transform domain UserPublic → presentation UserRowViewModel.

        Args:
            user: Domain user model
            admin_count: Number of admins (disables demote if last admin)
        """
        is_admin = user.role == UserRole.ADMIN
        # If admin_count not provided, assume actions are allowed
        can_mutate_admin = admin_count is None or admin_count > 1

        return cls(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            # Role badge
            role_label="Admin" if is_admin else "User",
            role_badge_color="bg-primary-500 text-white"
            if is_admin
            else "bg-stone-200 text-stone-900",
            # Button visibility
            show_promote=not is_admin,
            show_demote=is_admin and can_mutate_admin,
        )


class UserProfileViewModel(BaseModel):
    """Template-ready user profile for dashboard and navigation."""

    display_name: str
    email: str
    member_since: str  # Pre-formatted date string
    avatar_initial: str  # First letter of display name, uppercased
    is_admin: bool

    @classmethod
    def from_domain(cls, user: UserPublic) -> UserProfileViewModel:
        """Transform domain UserPublic → presentation UserProfileViewModel."""
        return cls(
            display_name=user.display_name,
            email=user.email,
            member_since=user.created_at.strftime("%B %d, %Y"),
            avatar_initial=user.display_name[0].upper() if user.display_name else "U",
            is_admin=user.role == UserRole.ADMIN,
        )
