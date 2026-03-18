"""View models for template rendering — all display logic lives here.

View models transform domain models into template-ready representations
with pre-computed display strings, CSS classes, and visibility flags.
This keeps templates dumb (no logic) and makes presentation decisions testable.
"""

from typing import Literal

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
    status_label: str
    status_badge_color: str
    status_filter: Literal["active", "deactivated"]

    # Button visibility flags
    show_promote: bool
    show_demote: bool
    show_deactivate: bool
    show_reactivate: bool

    @classmethod
    def from_domain(
        cls, user: UserPublic, active_admin_count: int | None = None
    ) -> UserRowViewModel:
        """Transform domain UserPublic → presentation UserRowViewModel.

        Args:
            user: Domain user model
            active_admin_count: Number of active admins (disables demote/deactivate
                if last admin)
        """
        is_admin = user.role == UserRole.ADMIN
        is_active = user.is_active
        # If active_admin_count not provided, assume actions are allowed
        can_mutate_admin = active_admin_count is None or active_admin_count > 1

        return cls(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            # Role badge
            role_label="Admin" if is_admin else "User",
            role_badge_color="bg-primary-500 text-white"
            if is_admin
            else "bg-stone-200 text-stone-900",
            # Status badge
            status_label="Active" if is_active else "Deactivated",
            status_badge_color="bg-green-700 text-white" if is_active else "bg-red-700 text-white",
            status_filter="active" if is_active else "deactivated",
            # Button visibility - only active users can be promoted/demoted/deactivated
            # Both demote and deactivate disabled if they're the last active admin
            show_promote=is_active and not is_admin,
            show_demote=is_active and is_admin and can_mutate_admin,
            show_deactivate=is_active and (not is_admin or can_mutate_admin),
            show_reactivate=not is_active,
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


class AuditEntryViewModel(BaseModel):
    """Template-ready audit log entry."""

    actor_name: str
    action: str
    timestamp: str  # Pre-formatted timestamp
    old_value: str | None
    new_value: str | None
    badge_label: str  # Simplified action label for badge
    badge_color: str  # Tailwind classes for badge

    @classmethod
    def from_dict(cls, entry: dict) -> AuditEntryViewModel:
        """Transform query result dict → presentation AuditEntryViewModel."""
        action_lower = entry["action"].lower()

        # Determine badge styling based on action type
        if "deactivate" in action_lower and "reactivate" not in action_lower:
            badge_label = "Deactivate"
            badge_color = "bg-red-100 text-red-800"
        elif "reactivate" in action_lower:
            badge_label = "Reactivate"
            badge_color = "bg-green-100 text-green-800"
        else:
            badge_label = entry["action"]
            badge_color = "bg-stone-100 text-stone-800"

        return cls(
            actor_name=entry["actor_name"],
            action=entry["action"],
            timestamp=entry["occurred_at"].strftime("%H:%M, %b %d"),
            old_value=entry.get("old_value"),
            new_value=entry.get("new_value"),
            badge_label=badge_label,
            badge_color=badge_color,
        )
