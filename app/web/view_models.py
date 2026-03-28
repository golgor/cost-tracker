"""View models for template rendering — all display logic lives here.

View models transform domain models into template-ready representations
with pre-computed display strings, CSS classes, and visibility flags.
This keeps templates dumb (no logic) and makes presentation decisions testable.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.domain.models import (
    ExpensePublic,
    ExpenseStatus,
    RecurringDefinitionPublic,
    RecurringFrequency,
    SettlementPublic,
    SettlementTransactionPublic,
    UserPublic,
    UserRole,
)
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


class ExpenseCardViewModel(BaseModel):
    """Template-ready representation of an expense card.

    Replaces the pattern of passing raw ExpensePublic + users dict to templates.
    All display logic (initials, formatting, badge color) is computed here.
    """

    id: int
    description: str
    amount: Decimal
    date: date
    formatted_date: str
    currency: str
    currency_symbol: str
    payer_id: int
    payer_display_name: str
    payer_initials: str
    is_current_user_payer: bool
    is_settled: bool
    is_gift: bool
    is_pending: bool
    is_recurring: bool
    is_auto_generated: bool
    recurring_definition_id: int | None
    show_edit_button: bool
    show_delete_button: bool

    @classmethod
    def from_domain(
        cls,
        expense: ExpensePublic,
        payer_name: str,
        currency_symbol: str,
        current_user_id: int,
        recurring_name: str | None = None,
    ) -> ExpenseCardViewModel:
        """Transform domain ExpensePublic into a template-ready view model.

        Args:
            expense: Domain expense model
            payer_name: Display name of the payer
            currency_symbol: Currency symbol for display (e.g., "$")
            current_user_id: ID of the currently logged-in user
            recurring_name: Name of the recurring definition, if any
        """
        is_settled = expense.status == ExpenseStatus.SETTLED
        return cls(
            id=expense.id,
            description=expense.description or "Expense",
            amount=expense.amount,
            date=expense.date,
            formatted_date=expense.date.strftime("%B %d, %Y"),
            currency=expense.currency,
            currency_symbol=currency_symbol,
            payer_id=expense.payer_id,
            payer_display_name=payer_name,
            payer_initials=_initials(payer_name),
            is_current_user_payer=expense.payer_id == current_user_id,
            is_settled=is_settled,
            is_gift=expense.status == ExpenseStatus.GIFT,
            is_pending=expense.status == ExpenseStatus.PENDING,
            is_recurring=expense.recurring_definition_id is not None,
            is_auto_generated=expense.is_auto_generated,
            recurring_definition_id=expense.recurring_definition_id,
            show_edit_button=not is_settled,
            show_delete_button=not is_settled,
        )


class SettlementHistoryViewModel(BaseModel):
    """Template-ready representation of a settlement in the history list.

    Replaces the manually-built dict in settlement_history_page.
    """

    id: int
    reference_id: str
    settled_at: str
    expense_count: int
    total_amount: Decimal
    has_amount: bool
    transaction_count: int
    transaction_summaries: list[dict[str, str]]

    @classmethod
    def from_domain(
        cls,
        settlement: SettlementPublic,
        expense_count: int,
        transactions: list[SettlementTransactionPublic],
        display_names: dict[int, str],
    ) -> SettlementHistoryViewModel:
        """Transform domain settlement + related data into a template-ready view model.

        Args:
            settlement: Domain settlement model
            expense_count: Number of expenses in this settlement
            transactions: List of settlement transactions
            display_names: Mapping of user IDs to display names
        """
        total_amount = sum(tx.amount for tx in transactions)
        summaries = [
            {
                "from_name": display_names.get(tx.from_user_id, f"User {tx.from_user_id}"),
                "to_name": display_names.get(tx.to_user_id, f"User {tx.to_user_id}"),
            }
            for tx in transactions
        ]
        return cls(
            id=settlement.id,
            reference_id=settlement.reference_id,
            settled_at=settlement.settled_at.strftime("%b %d, %Y"),
            expense_count=expense_count,
            total_amount=total_amount,
            has_amount=total_amount > 0,
            transaction_count=len(transactions),
            transaction_summaries=summaries,
        )
