"""Unit tests for RecurringDefinitionViewModel new fields."""

from datetime import date, datetime
from decimal import Decimal

from app.domain.models import RecurringDefinitionPublic, RecurringFrequency, SplitType
from app.web.view_models import RecurringDefinitionViewModel

_MEMBER_IDS = [1, 2]
_MEMBER_NAMES = {1: "Robert", 2: "Anna"}


def _make_defn(
    split_type: SplitType = SplitType.EVEN,
    split_config: dict | None = None,
    amount: Decimal = Decimal("100.00"),
    category: str | None = "subscription",
    next_due_date: date = date(2026, 4, 12),
    payer_id: int = 1,
    frequency: RecurringFrequency = RecurringFrequency.MONTHLY,
) -> RecurringDefinitionPublic:
    return RecurringDefinitionPublic(
        id=1,
        name="Test",
        amount=amount,
        frequency=frequency,
        next_due_date=next_due_date,
        payer_id=payer_id,
        split_type=split_type,
        split_config=split_config,
        category=category,
        auto_generate=False,
        is_active=True,
        currency="EUR",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


def _vm(**kwargs) -> RecurringDefinitionViewModel:
    return RecurringDefinitionViewModel.from_domain(
        _make_defn(**kwargs), "Robert", _MEMBER_IDS, _MEMBER_NAMES
    )


class TestIsPersonal:
    def test_even_split_is_not_personal(self):
        assert _vm(split_type=SplitType.EVEN).is_personal is False

    def test_percentage_zero_one_user_is_personal(self):
        assert (
            _vm(split_type=SplitType.PERCENTAGE, split_config={1: "100", 2: "0"}).is_personal
            is True
        )

    def test_shares_zero_one_user_is_personal(self):
        assert _vm(split_type=SplitType.SHARES, split_config={1: "1", 2: "0"}).is_personal is True

    def test_exact_zero_one_user_is_personal(self):
        assert (
            _vm(split_type=SplitType.EXACT, split_config={1: "100.00", 2: "0.00"}).is_personal
            is True
        )

    def test_both_nonzero_is_not_personal(self):
        assert (
            _vm(split_type=SplitType.PERCENTAGE, split_config={1: "70", 2: "30"}).is_personal
            is False
        )

    def test_no_split_config_is_not_personal(self):
        assert _vm(split_type=SplitType.PERCENTAGE, split_config=None).is_personal is False


class TestPersonalOwnerId:
    def test_returns_nonzero_user_id(self):
        vm = _vm(split_type=SplitType.PERCENTAGE, split_config={1: "100", 2: "0"})
        assert vm.personal_owner_id == 1

    def test_none_for_shared(self):
        assert _vm(split_type=SplitType.EVEN).personal_owner_id is None


class TestPerPersonMonthlyCost:
    def test_even_split_divides_equally(self):
        vm = _vm(amount=Decimal("100.00"), split_type=SplitType.EVEN)
        assert vm.per_person_monthly_cost == {1: "50.00", 2: "50.00"}

    def test_percentage_split_scales_to_monthly(self):
        vm = _vm(
            amount=Decimal("100.00"),
            split_type=SplitType.PERCENTAGE,
            split_config={1: "70", 2: "30"},
        )
        assert vm.per_person_monthly_cost == {1: "70.00", 2: "30.00"}

    def test_yearly_normalizes_to_monthly(self):
        vm = _vm(
            amount=Decimal("120.00"),
            frequency=RecurringFrequency.YEARLY,
            split_type=SplitType.PERCENTAGE,
            split_config={1: "100", 2: "0"},
        )
        assert vm.per_person_monthly_cost[1] == "10.00"
        assert vm.per_person_monthly_cost[2] == "0.00"

    def test_shares_split(self):
        vm = _vm(
            amount=Decimal("100.00"),
            split_type=SplitType.SHARES,
            split_config={1: "3", 2: "1"},
        )
        assert vm.per_person_monthly_cost[1] == "75.00"
        assert vm.per_person_monthly_cost[2] == "25.00"


class TestDisplayHelpers:
    def test_next_due_date_display_format(self):
        vm = _vm(next_due_date=date(2026, 4, 12))
        assert vm.next_due_date_display == "Apr 12, 2026"

    def test_category_border_color_subscription(self):
        assert _vm(category="subscription").category_border_color == "#6366f1"

    def test_category_border_color_insurance(self):
        assert _vm(category="insurance").category_border_color == "#f59e0b"

    def test_category_border_color_membership(self):
        assert _vm(category="membership").category_border_color == "#ec4899"

    def test_category_border_color_utilities(self):
        assert _vm(category="utilities").category_border_color == "#10b981"

    def test_category_border_color_none_uses_default(self):
        assert _vm(category=None).category_border_color == "#a8a29e"
