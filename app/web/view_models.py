"""View models for template rendering — all display logic lives here.

View models transform domain models into template-ready representations
with pre-computed display strings, CSS classes, and visibility flags.
This keeps templates dumb (no logic) and makes presentation decisions testable.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pydantic import BaseModel

from app.domain.models import (
    ExpensePublic,
    ExpenseStatus,
    RecurringDefinitionPublic,
    RecurringFrequency,
    SettlementPublic,
    SettlementTransactionPublic,
    SplitType,
    UserPublic,
)
from app.domain.recurring import normalized_monthly_cost

_FREQUENCY_LABELS: dict[RecurringFrequency, str] = {
    RecurringFrequency.MONTHLY: "monthly",
    RecurringFrequency.QUARTERLY: "quarterly",
    RecurringFrequency.SEMI_ANNUALLY: "semi-annually",
    RecurringFrequency.YEARLY: "yearly",
    RecurringFrequency.EVERY_N_MONTHS: "every N months",
}

_CATEGORY_BORDER_COLORS: dict[str | None, str] = {
    "subscription": "#6366f1",
    "insurance": "#f59e0b",
    "membership": "#ec4899",
    "utilities": "#10b981",
    "childcare": "#0ea5e9",
}
_DEFAULT_BORDER_COLOR = "#a8a29e"
_TWO_PLACES = Decimal("0.01")


def _initials(display_name: str) -> str:
    """Extract up to two uppercase initials from a display name."""
    parts = display_name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _category_border_color(category: str | None) -> str:
    return _CATEGORY_BORDER_COLORS.get(category, _DEFAULT_BORDER_COLOR)


def _detect_personal(
    split_type: SplitType,
    split_config: dict | None,
) -> tuple[bool, int | None]:
    """Return (is_personal, personal_owner_id).
    Personal: exactly one user has value 0, the other has nonzero share.
    """
    if split_type == SplitType.EVEN or not split_config:
        return False, None
    zero_keys = [k for k, v in split_config.items() if Decimal(str(v)) == 0]
    nonzero_keys = [k for k in split_config if k not in zero_keys]
    if len(zero_keys) == 1 and len(nonzero_keys) == 1:
        return True, int(nonzero_keys[0])
    return False, None


def _compute_per_person_cost(
    split_type: SplitType,
    split_config: dict | None,
    member_ids: list[int],
    monthly_cost: Decimal,
    amount: Decimal,
) -> dict[int, str]:
    """Return {user_id: formatted_monthly_cost} for all members."""
    if split_type == SplitType.EVEN:
        count = len(member_ids) or 1
        per = (monthly_cost / count).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        return {uid: str(per) for uid in member_ids}

    if not split_config:
        return {}

    if split_type == SplitType.PERCENTAGE:
        return {
            int(k): str(
                (monthly_cost * Decimal(str(v)) / 100).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            )
            for k, v in split_config.items()
        }

    if split_type == SplitType.SHARES:
        total = sum(Decimal(str(v)) for v in split_config.values())
        if total == 0:
            return {}
        return {
            int(k): str(
                (monthly_cost * Decimal(str(v)) / total).quantize(
                    _TWO_PLACES, rounding=ROUND_HALF_UP
                )
            )
            for k, v in split_config.items()
        }

    if split_type == SplitType.EXACT:
        if amount == 0:
            return {}
        return {
            int(k): str(
                (monthly_cost * Decimal(str(v)) / amount).quantize(
                    _TWO_PLACES, rounding=ROUND_HALF_UP
                )
            )
            for k, v in split_config.items()
        }

    return {}


class UserRowViewModel(BaseModel):
    """Template-ready representation of a user row in admin table."""

    id: int
    display_name: str
    email: str

    @classmethod
    def from_domain(cls, user: UserPublic) -> UserRowViewModel:
        """Transform domain UserPublic → presentation UserRowViewModel."""
        return cls(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
        )


class UserProfileViewModel(BaseModel):
    """Template-ready user profile for dashboard and navigation."""

    display_name: str
    email: str
    member_since: str  # Pre-formatted date string
    avatar_initial: str  # First letter of display name, uppercased

    @classmethod
    def from_domain(cls, user: UserPublic) -> UserProfileViewModel:
        """Transform domain UserPublic → presentation UserProfileViewModel."""
        return cls(
            display_name=user.display_name,
            email=user.email,
            member_since=user.created_at.strftime("%B %d, %Y"),
            avatar_initial=user.display_name[0].upper() if user.display_name else "U",
        )


class RecurringDefinitionViewModel(BaseModel):
    """Template-ready representation of a recurring definition."""

    id: int
    name: str
    amount: Decimal
    frequency_label: str
    interval_months: int | None
    next_due_date: date
    next_due_date_display: str
    payer_display_name: str
    payer_initials: str
    split_type: str
    category: str | None
    category_border_color: str
    currency: str
    normalized_monthly_cost: str
    is_auto_generate: bool
    is_manual_mode: bool
    is_active: bool
    is_even_split: bool
    is_personal: bool
    personal_owner_id: int | None
    per_person_monthly_cost: dict[int, str]
    split_pills: list[dict[str, str]]  # [{"initials": "R", "cost": "10.00"}]

    @classmethod
    def from_domain(
        cls,
        defn: RecurringDefinitionPublic,
        payer_name: str,
        member_ids: list[int],
        member_names: dict[int, str],
    ) -> RecurringDefinitionViewModel:
        """Transform domain model + member context → template-ready view model."""
        frequency_label = _FREQUENCY_LABELS.get(defn.frequency, defn.frequency.value.lower())
        if defn.frequency == RecurringFrequency.EVERY_N_MONTHS and defn.interval_months:
            frequency_label = f"every {defn.interval_months} months"

        monthly_cost = normalized_monthly_cost(defn.amount, defn.frequency, defn.interval_months)
        is_personal, personal_owner_id = _detect_personal(defn.split_type, defn.split_config)
        per_person = _compute_per_person_cost(
            defn.split_type, defn.split_config, member_ids, monthly_cost, defn.amount
        )
        split_pills = [
            {"initials": _initials(member_names.get(uid, "?")), "cost": cost}
            for uid, cost in per_person.items()
        ]

        return cls(
            id=defn.id,
            name=defn.name,
            amount=defn.amount,
            frequency_label=frequency_label,
            interval_months=defn.interval_months,
            next_due_date=defn.next_due_date,
            next_due_date_display=defn.next_due_date.strftime("%b %-d, %Y"),
            payer_display_name=payer_name,
            payer_initials=_initials(payer_name),
            split_type=defn.split_type.value.title(),
            category=defn.category,
            category_border_color=_category_border_color(defn.category),
            currency=defn.currency,
            normalized_monthly_cost=str(monthly_cost),
            is_auto_generate=defn.auto_generate,
            is_manual_mode=not defn.auto_generate,
            is_active=defn.is_active,
            is_even_split=defn.split_type == SplitType.EVEN,
            is_personal=is_personal,
            personal_owner_id=personal_owner_id,
            per_person_monthly_cost=per_person,
            split_pills=split_pills,
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
    recurring_name: str | None
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
            recurring_name=recurring_name
            or ("Recurring" if expense.recurring_definition_id else None),
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
        total_amount = sum((tx.amount for tx in transactions), Decimal("0"))
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


def compute_registry_stats(
    definitions: list[RecurringDefinitionViewModel],
    member_names: dict[int, str],
) -> dict[str, Any]:
    """Compute shared/personal/total monthly cost breakdown from view models.

    Returns:
        - shared_monthly_total (str)
        - personal_monthly_totals (dict[int, str])
        - per_person_shared_cost (dict[int, str])
        - total_monthly_cost (str)
        - active_count (int)
        - has_active_definitions (bool)
        - active_plural (str)
        - member_stats (list[dict]) — per-member breakdown for summary bar
        - currency (str)
    """
    from app.settings import settings

    _TWO = Decimal("0.01")
    shared_total = Decimal("0")
    personal_totals: dict[int, Decimal] = {}
    per_person_shared: dict[int, Decimal] = {}
    grand_total = Decimal("0")

    for defn in definitions:
        monthly = Decimal(defn.normalized_monthly_cost)
        grand_total += monthly

        if defn.is_personal and defn.personal_owner_id is not None:
            uid = defn.personal_owner_id
            personal_totals[uid] = personal_totals.get(uid, Decimal("0")) + monthly
        else:
            shared_total += monthly
            for uid, cost_str in defn.per_person_monthly_cost.items():
                cost = Decimal(cost_str)
                per_person_shared[uid] = per_person_shared.get(uid, Decimal("0")) + cost

    member_stats = [
        {
            "initials": _initials(name),
            "shared_cost": str(
                per_person_shared.get(uid, Decimal("0")).quantize(_TWO, rounding=ROUND_HALF_UP)
            ),
            "personal_cost": str(
                personal_totals.get(uid, Decimal("0")).quantize(_TWO, rounding=ROUND_HALF_UP)
            ),
        }
        for uid, name in member_names.items()
    ]

    count = len(definitions)
    return {
        "shared_monthly_total": str(shared_total.quantize(_TWO, rounding=ROUND_HALF_UP)),
        "personal_monthly_totals": {
            uid: str(v.quantize(_TWO, rounding=ROUND_HALF_UP)) for uid, v in personal_totals.items()
        },
        "per_person_shared_cost": {
            uid: str(v.quantize(_TWO, rounding=ROUND_HALF_UP))
            for uid, v in per_person_shared.items()
        },
        "total_monthly_cost": str(grand_total.quantize(_TWO, rounding=ROUND_HALF_UP)),
        "active_count": count,
        "has_active_definitions": count > 0,
        "active_plural": "s" if count != 1 else "",
        "member_stats": member_stats,
        "currency": settings.DEFAULT_CURRENCY,
    }
