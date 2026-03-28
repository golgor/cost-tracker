"""View models for template rendering — all display logic lives here.

View models transform domain models into template-ready representations
with pre-computed display strings, CSS classes, and visibility flags.
This keeps templates dumb (no logic) and makes presentation decisions testable.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.domain.models import RecurringDefinitionPublic, RecurringFrequency, UserPublic, UserRole
from app.domain.recurring import normalized_monthly_cost

_FREQUENCY_LABELS: dict[RecurringFrequency, str] = {
    RecurringFrequency.MONTHLY: "monthly",
    RecurringFrequency.QUARTERLY: "quarterly",
    RecurringFrequency.SEMI_ANNUALLY: "semi-annually",
    RecurringFrequency.YEARLY: "yearly",
    RecurringFrequency.EVERY_N_MONTHS: "every N months",
}


def _initials(display_name: str) -> str:
    """Extract up to two uppercase initials from a display name."""
    parts = display_name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


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


class RecurringDefinitionViewModel(BaseModel):
    """Template-ready representation of a recurring definition."""

    id: int
    name: str
    amount: Decimal
    frequency_label: str
    interval_months: int | None
    next_due_date: date
    payer_display_name: str
    payer_initials: str
    split_type: str
    category: str | None
    currency: str
    normalized_monthly_cost: str
    is_auto_generate: bool
    is_manual_mode: bool
    is_active: bool

    @classmethod
    def from_domain(
        cls, defn: RecurringDefinitionPublic, payer_name: str
    ) -> RecurringDefinitionViewModel:
        """Transform domain RecurringDefinitionPublic + payer name → view model.

        All display logic (frequency labels, initials, normalized cost) is computed here
        so templates remain free of business logic.
        """
        frequency_label = _FREQUENCY_LABELS.get(defn.frequency, defn.frequency.value.lower())
        if defn.frequency == RecurringFrequency.EVERY_N_MONTHS and defn.interval_months:
            frequency_label = f"every {defn.interval_months} months"

        monthly_cost = normalized_monthly_cost(defn.amount, defn.frequency, defn.interval_months)

        return cls(
            id=defn.id,
            name=defn.name,
            amount=defn.amount,
            frequency_label=frequency_label,
            interval_months=defn.interval_months,
            next_due_date=defn.next_due_date,
            payer_display_name=payer_name,
            payer_initials=_initials(payer_name),
            split_type=defn.split_type.value.title(),
            category=defn.category,
            currency=defn.currency,
            normalized_monthly_cost=str(monthly_cost),
            is_auto_generate=defn.auto_generate,
            is_manual_mode=not defn.auto_generate,
            is_active=defn.is_active,
        )
