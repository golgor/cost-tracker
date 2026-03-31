# Recurring Cost Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the `/recurring` page with redesigned cards, filter chips, an extended summary stats bar, and a "Make Personal" form toggle.

**Architecture:** All display logic lives in `RecurringDefinitionViewModel` (view model layer); templates remain logic-free. The new `GET /recurring/filtered` HTMX endpoint returns the `_definition_list` partial so summary bar and card list update together. "Personal" is derived from existing `split_config` — no DB changes.

**Tech Stack:** FastAPI, Jinja2, HTMX, Tailwind CSS, SQLModel/SQLAlchemy, pytest, pydantic BaseModel

---

## File Structure

**Modified:**
- `app/web/view_models.py` — add 5 fields to `RecurringDefinitionViewModel`, add `compute_registry_stats()`
- `app/web/recurring.py` — refactor `_to_view_models()`, add `/recurring/filtered` route, add `active_categories` + `is_personal_edit` to contexts
- `app/adapters/sqlalchemy/queries/recurring_queries.py` — add `get_filtered_definitions()`
- `app/templates/recurring/_definition_card.html` — full rewrite
- `app/templates/recurring/_summary_bar.html` — rewrite as stats grid
- `app/templates/recurring/index.html` — add filter chips
- `app/templates/recurring/_definition_list.html` — add filter chips (for HTMX partial)
- `app/templates/recurring/form.html` — add "Make Personal" toggle + JS
- `tests/web/recurring_test.py` — filter endpoint + card content + summary + form tests

**Created:**
- `tests/web/view_models_test.py` — unit tests for new view model fields

---

## Task 1: View model fields — is_personal, per-person costs, display helpers

**Files:**
- Modify: `app/web/view_models.py`
- Create: `tests/web/view_models_test.py`

- [ ] **Step 1: Write failing tests**

Create `tests/web/view_models_test.py`:

```python
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
        assert _vm(split_type=SplitType.PERCENTAGE, split_config={1: "100", 2: "0"}).is_personal is True

    def test_shares_zero_one_user_is_personal(self):
        assert _vm(split_type=SplitType.SHARES, split_config={1: "1", 2: "0"}).is_personal is True

    def test_exact_zero_one_user_is_personal(self):
        assert _vm(split_type=SplitType.EXACT, split_config={1: "100.00", 2: "0.00"}).is_personal is True

    def test_both_nonzero_is_not_personal(self):
        assert _vm(split_type=SplitType.PERCENTAGE, split_config={1: "70", 2: "30"}).is_personal is False

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
        # €120/year = €10/mo; user 1 gets 100%
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
mise run test -- tests/web/view_models_test.py -v
```
Expected: multiple `FAILED` — `from_domain()` doesn't accept `member_ids`/`member_names` yet.

- [ ] **Step 3: Implement view model additions in `app/web/view_models.py`**

Add imports at top of file (after existing imports):
```python
from decimal import ROUND_HALF_UP
from typing import Any
```

Add these helper functions after the existing `_initials` function:

```python
_CATEGORY_BORDER_COLORS: dict[str | None, str] = {
    "subscription": "#6366f1",
    "insurance": "#f59e0b",
    "membership": "#ec4899",
    "utilities": "#10b981",
    "childcare": "#0ea5e9",
}
_DEFAULT_BORDER_COLOR = "#a8a29e"
_TWO_PLACES = Decimal("0.01")


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
                (monthly_cost * Decimal(str(v)) / total).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            )
            for k, v in split_config.items()
        }

    if split_type == SplitType.EXACT:
        if amount == 0:
            return {}
        return {
            int(k): str(
                (monthly_cost * Decimal(str(v)) / amount).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            )
            for k, v in split_config.items()
        }

    return {}
```

Replace the entire `RecurringDefinitionViewModel` class with:

```python
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
    is_personal: bool
    personal_owner_id: int | None
    per_person_monthly_cost: dict[int, str]
    split_pills: list[dict[str, str]]  # [{"initials": "R", "cost": "10.00"}]
    is_even_split: bool  # pre-computed for template visibility (no string comparisons in templates)

    @classmethod
    def from_domain(
        cls,
        defn: RecurringDefinitionPublic,
        payer_name: str,
        member_ids: list[int],
        member_names: dict[int, str],
    ) -> "RecurringDefinitionViewModel":
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
mise run test -- tests/web/view_models_test.py -v
```
Expected: all PASSED.

- [ ] **Step 5: Run lint**

```bash
mise run lint:fix
```

- [ ] **Step 6: Commit**

```bash
git add app/web/view_models.py tests/web/view_models_test.py
git commit -m "feat: add is_personal, per_person_cost, display helpers to RecurringDefinitionViewModel"
```

---

## Task 2: compute_registry_stats + update _to_view_models + route callers

**Files:**
- Modify: `app/web/view_models.py` — add `compute_registry_stats()`
- Modify: `app/web/recurring.py` — refactor `_to_view_models()`, replace `get_registry_summary` calls

- [ ] **Step 1: Write failing tests**

Add to `tests/web/view_models_test.py`:

```python
from unittest.mock import MagicMock
from app.web.view_models import compute_registry_stats


def _mock_vm(is_personal, personal_owner_id, monthly_cost, per_person):
    vm = MagicMock(spec=RecurringDefinitionViewModel)
    vm.is_personal = is_personal
    vm.personal_owner_id = personal_owner_id
    vm.normalized_monthly_cost = monthly_cost
    vm.per_person_monthly_cost = per_person
    return vm


class TestComputeRegistryStats:
    _NAMES = {1: "Robert", 2: "Anna"}

    def test_all_shared(self):
        vms = [
            _mock_vm(False, None, "50.00", {1: "25.00", 2: "25.00"}),
            _mock_vm(False, None, "30.00", {1: "15.00", 2: "15.00"}),
        ]
        stats = compute_registry_stats(vms, self._NAMES)
        assert stats["shared_monthly_total"] == "80.00"
        assert stats["total_monthly_cost"] == "80.00"
        assert stats["personal_monthly_totals"] == {}

    def test_personal_isolated(self):
        vms = [_mock_vm(True, 1, "35.00", {1: "35.00", 2: "0.00"})]
        stats = compute_registry_stats(vms, self._NAMES)
        assert stats["shared_monthly_total"] == "0.00"
        assert stats["personal_monthly_totals"] == {1: "35.00"}
        assert stats["total_monthly_cost"] == "35.00"

    def test_mixed(self):
        vms = [
            _mock_vm(False, None, "20.00", {1: "10.00", 2: "10.00"}),
            _mock_vm(True, 2, "40.00", {1: "0.00", 2: "40.00"}),
        ]
        stats = compute_registry_stats(vms, self._NAMES)
        assert stats["shared_monthly_total"] == "20.00"
        assert stats["personal_monthly_totals"] == {2: "40.00"}
        assert stats["total_monthly_cost"] == "60.00"
        assert stats["active_count"] == 2

    def test_member_stats_contains_initials(self):
        vms = [_mock_vm(False, None, "20.00", {1: "10.00", 2: "10.00"})]
        stats = compute_registry_stats(vms, self._NAMES)
        initials = [m["initials"] for m in stats["member_stats"]]
        assert "R" in initials
        assert "A" in initials
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
mise run test -- tests/web/view_models_test.py::TestComputeRegistryStats -v
```
Expected: `FAILED` — `compute_registry_stats` not found.

- [ ] **Step 3: Add `compute_registry_stats` to `app/web/view_models.py`**

Add after the `RecurringDefinitionViewModel` class:

```python
def compute_registry_stats(
    definitions: list[RecurringDefinitionViewModel],
    member_names: dict[int, str],
) -> dict[str, Any]:
    """Compute shared/personal/total monthly cost breakdown from view models.

    Returns dict with:
    - shared_monthly_total (str)
    - personal_monthly_totals (dict[int, str])
    - per_person_shared_cost (dict[int, str])
    - total_monthly_cost (str)
    - active_count (int)
    - has_active_definitions (bool)
    - active_plural (str)
    - member_stats (list[dict]) — per-member cost breakdown for summary bar display
    """
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
                per_person_shared.get(uid, Decimal("0")).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            ),
            "personal_cost": str(
                personal_totals.get(uid, Decimal("0")).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
            ),
        }
        for uid, name in member_names.items()
    ]

    return {
        "shared_monthly_total": str(shared_total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)),
        "personal_monthly_totals": {
            uid: str(v.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))
            for uid, v in personal_totals.items()
        },
        "per_person_shared_cost": {
            uid: str(v.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))
            for uid, v in per_person_shared.items()
        },
        "total_monthly_cost": str(grand_total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)),
        "active_count": len(definitions),
        "has_active_definitions": len(definitions) > 0,
        "active_plural": "s" if len(definitions) != 1 else "",
        "member_stats": member_stats,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
mise run test -- tests/web/view_models_test.py::TestComputeRegistryStats -v
```
Expected: all PASSED.

- [ ] **Step 5: Refactor `_to_view_models` in `app/web/recurring.py`**

Replace the existing function:

```python
def _to_view_models(
    definitions: list[RecurringDefinitionPublic],
    uow: UnitOfWork,
    member_names: dict[int, str],
) -> list[RecurringDefinitionViewModel]:
    """Convert domain models to template-ready view models."""
    member_ids = list(member_names.keys())
    return [
        RecurringDefinitionViewModel.from_domain(
            d, member_names.get(d.payer_id, "Unknown"), member_ids, member_names
        )
        for d in definitions
    ]
```

- [ ] **Step 6: Update `registry_index` route to pass member_names**

Replace the route body:

```python
@router.get("/recurring", response_class=HTMLResponse)
async def registry_index(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """Render the recurring definitions registry (Active tab by default)."""
    with uow:
        user = uow.users.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        all_users = get_all_users(uow.session)
        member_names = {u.id: u.display_name for u in all_users}

        domain_defs = get_active_definitions(uow.session)
        active_categories = sorted({d.category for d in domain_defs if d.category})
        definitions = _to_view_models(domain_defs, uow, member_names)
        summary = compute_registry_stats(definitions, member_names)

    return templates.TemplateResponse(
        request,
        "recurring/index.html",
        {
            "user": user,
            "definitions": definitions,
            "summary": summary,
            "active_tab": "active",
            "active_categories": active_categories,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
```

- [ ] **Step 7: Update `registry_tab` route**

Replace the route body:

```python
@router.get("/recurring/tab/{tab}", response_class=HTMLResponse)
async def registry_tab(
    request: Request,
    tab: str,
    user_id: CurrentUserId,
    uow: UowDep,
):
    """HTMX partial: switch between Active and Paused tabs."""
    if tab not in ("active", "paused"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tab")

    with uow:
        all_users = get_all_users(uow.session)
        member_names = {u.id: u.display_name for u in all_users}

        all_active = get_active_definitions(uow.session)
        active_categories = sorted({d.category for d in all_active if d.category})

        if tab == "active":
            domain_defs = all_active
        else:
            domain_defs = get_paused_definitions(uow.session)

        definitions = _to_view_models(domain_defs, uow, member_names)
        summary = compute_registry_stats(definitions, member_names)

    return templates.TemplateResponse(
        request,
        "recurring/_definition_list.html",
        {
            "definitions": definitions,
            "summary": summary,
            "active_tab": tab,
            "active_categories": active_categories,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
```

Also update `toggle_active` and `create_expense_for_definition` routes — they call `_to_view_models([updated], uow)`. Update to:
```python
all_users = get_all_users(uow.session)
member_names = {u.id: u.display_name for u in all_users}
view_models = _to_view_models([updated], uow, member_names)
```

Add `compute_registry_stats` to imports in `recurring.py`:
```python
from app.web.view_models import RecurringDefinitionViewModel, compute_registry_stats
```

Remove the `get_registry_summary` import (no longer used).

- [ ] **Step 8: Run all recurring tests**

```bash
mise run test -- tests/web/recurring_test.py -v
```
Expected: all PASSED. (The `test_summary_bar_shows_count` test checks "1 active cost" — `active_plural` still works from `compute_registry_stats`.)

- [ ] **Step 9: Run lint**

```bash
mise run lint:fix
```

- [ ] **Step 10: Commit**

```bash
git add app/web/view_models.py app/web/recurring.py tests/web/view_models_test.py
git commit -m "feat: add compute_registry_stats, refactor _to_view_models with member context"
```

---

## Task 3: Filter query and /recurring/filtered endpoint

**Files:**
- Modify: `app/adapters/sqlalchemy/queries/recurring_queries.py`
- Modify: `app/web/recurring.py`
- Modify: `tests/web/recurring_test.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/web/recurring_test.py`:

```python
class TestFilteredEndpoint:
    """Test the /recurring/filtered HTMX endpoint."""

    def _add_definition(self, uow, user, name="Netflix", amount="14.99",
                        category=None, split_type=SplitType.EVEN, split_config=None):
        row = RecurringDefinitionRow(
            name=name,
            amount=Decimal(amount),
            frequency=RecurringFrequency.MONTHLY,
            next_due_date=date(2026, 4, 1),
            payer_id=user.id,
            split_type=split_type,
            split_config=split_config,
            auto_generate=False,
            is_active=True,
            currency="EUR",
            category=category,
        )
        uow.session.add(row)
        uow.session.flush()
        return row

    def test_filtered_endpoint_returns_200(self, authenticated_client):
        response = authenticated_client.get(
            "/recurring/filtered",
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200

    def test_filtered_scope_all_returns_all_active(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user, name="Netflix")
        self._add_definition(uow, test_user, name="Spotify")
        response = authenticated_client.get("/recurring/filtered?scope=all")
        assert "Netflix" in response.text
        assert "Spotify" in response.text

    def test_filtered_scope_personal_shows_only_personal(self, authenticated_client, test_user, uow):
        with uow:
            partner = uow.users.save(
                oidc_sub="filter_partner@test.com",
                email="filter_partner@test.com",
                display_name="Filter Partner",
            )
        self._add_definition(
            uow, test_user, name="Gym",
            split_type=SplitType.PERCENTAGE,
            split_config={test_user.id: "100", partner.id: "0"},
        )
        self._add_definition(uow, test_user, name="Shared Netflix")
        response = authenticated_client.get("/recurring/filtered?scope=personal")
        assert "Gym" in response.text
        assert "Shared Netflix" not in response.text

    def test_filtered_scope_shared_excludes_personal(self, authenticated_client, test_user, uow):
        with uow:
            partner = uow.users.save(
                oidc_sub="filter_partner2@test.com",
                email="filter_partner2@test.com",
                display_name="Filter Partner2",
            )
        self._add_definition(
            uow, test_user, name="Personal Gym",
            split_type=SplitType.PERCENTAGE,
            split_config={test_user.id: "100", partner.id: "0"},
        )
        self._add_definition(uow, test_user, name="Shared Netflix")
        response = authenticated_client.get("/recurring/filtered?scope=shared")
        assert "Shared Netflix" in response.text
        assert "Personal Gym" not in response.text

    def test_filtered_by_category(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user, name="Netflix", category="subscription")
        self._add_definition(uow, test_user, name="Home Insurance", category="insurance")
        response = authenticated_client.get("/recurring/filtered?category=subscription")
        assert "Netflix" in response.text
        assert "Home Insurance" not in response.text

    def test_filtered_by_payer(self, authenticated_client, test_user, uow):
        with uow:
            second = uow.users.save(
                oidc_sub="filter_second@test.com",
                email="filter_second@test.com",
                display_name="Filter Second",
            )
        self._add_definition(uow, test_user, name="User1 Cost")
        self._add_definition(uow, second, name="User2 Cost")
        response = authenticated_client.get(f"/recurring/filtered?payer_id={test_user.id}")
        assert "User1 Cost" in response.text
        assert "User2 Cost" not in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
mise run test -- tests/web/recurring_test.py::TestFilteredEndpoint -v
```
Expected: all `FAILED` — route doesn't exist.

- [ ] **Step 3: Add `get_filtered_definitions` to `recurring_queries.py`**

Add after existing imports (add `from decimal import Decimal`):

```python
def _is_personal_domain(defn: RecurringDefinitionPublic) -> bool:
    """Return True if this definition is personal (one user bears 100% of the cost)."""
    if defn.split_type.value == "EVEN" or not defn.split_config:
        return False
    zero_count = sum(1 for v in defn.split_config.values() if Decimal(str(v)) == 0)
    nonzero_count = sum(1 for v in defn.split_config.values() if Decimal(str(v)) != 0)
    return zero_count == 1 and nonzero_count == 1


def get_filtered_definitions(
    session: Session,
    *,
    scope: str = "all",
    payer_id: int | None = None,
    category: str | None = None,
    active_only: bool = True,
) -> list[RecurringDefinitionPublic]:
    """Fetch filtered recurring definitions for the HTMX filter endpoint.

    Args:
        scope: "all" | "shared" | "personal"
        payer_id: Filter by payer.
        category: Filter by category string.
        active_only: If True, only return is_active=True rows.
    """
    statement = select(RecurringDefinitionRow).where(
        RecurringDefinitionRow.deleted_at.is_(None),  # type: ignore[union-attr]
    )

    if active_only:
        statement = statement.where(
            RecurringDefinitionRow.is_active.is_(True),  # type: ignore[union-attr]
        )
    if payer_id is not None:
        statement = statement.where(RecurringDefinitionRow.payer_id == payer_id)
    if category is not None:
        statement = statement.where(RecurringDefinitionRow.category == category)

    statement = statement.order_by(RecurringDefinitionRow.next_due_date)  # type: ignore[arg-type]
    rows = session.exec(statement).all()
    results = [_row_to_public(row) for row in rows]

    if scope == "personal":
        results = [r for r in results if _is_personal_domain(r)]
    elif scope == "shared":
        results = [r for r in results if not _is_personal_domain(r)]

    return results
```

- [ ] **Step 4: Add `GET /recurring/filtered` route to `app/web/recurring.py`**

Add after the `registry_tab` route. Also add `get_filtered_definitions` to the imports from `recurring_queries`:

```python
@router.get("/recurring/filtered", response_class=HTMLResponse)
async def registry_filtered(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
    scope: str = "all",
    payer_id: int | None = None,
    category: str | None = None,
    tab: str = "active",
):
    """HTMX partial: filtered definition list + updated summary bar."""
    active_only = tab != "paused"

    with uow:
        all_users = get_all_users(uow.session)
        member_names = {u.id: u.display_name for u in all_users}

        all_active = get_active_definitions(uow.session)
        active_categories = sorted({d.category for d in all_active if d.category})

        domain_defs = get_filtered_definitions(
            uow.session,
            scope=scope,
            payer_id=payer_id,
            category=category,
            active_only=active_only,
        )
        definitions = _to_view_models(domain_defs, uow, member_names)
        summary = compute_registry_stats(definitions, member_names)

    return templates.TemplateResponse(
        request,
        "recurring/_definition_list.html",
        {
            "definitions": definitions,
            "summary": summary,
            "active_tab": tab,
            "active_categories": active_categories,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        },
    )
```

Update import in `recurring.py`:
```python
from app.adapters.sqlalchemy.queries.recurring_queries import (
    get_active_definitions,
    get_filtered_definitions,
    get_paused_definitions,
)
```

- [ ] **Step 5: Run tests**

```bash
mise run test -- tests/web/recurring_test.py -v
```
Expected: all PASSED.

- [ ] **Step 6: Run lint**

```bash
mise run lint:fix
```

- [ ] **Step 7: Commit**

```bash
git add app/adapters/sqlalchemy/queries/recurring_queries.py app/web/recurring.py tests/web/recurring_test.py
git commit -m "feat: add get_filtered_definitions and /recurring/filtered HTMX endpoint"
```

---

## Task 4: Rewrite _definition_card.html

**Files:**
- Modify: `app/templates/recurring/_definition_card.html`
- Modify: `tests/web/recurring_test.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/web/recurring_test.py`:

```python
class TestCardContent:
    """Test card rendering with the new view model fields."""

    def _add_definition(self, uow, user, **kwargs):
        defaults = dict(
            name="Netflix",
            amount=Decimal("19.99"),
            frequency=RecurringFrequency.MONTHLY,
            next_due_date=date(2027, 1, 15),
            payer_id=user.id,
            split_type=SplitType.EVEN,
            split_config=None,
            auto_generate=False,
            is_active=True,
            currency="EUR",
            category="subscription",
        )
        defaults.update(kwargs)
        row = RecurringDefinitionRow(**defaults)
        uow.session.add(row)
        uow.session.flush()
        return row

    def test_card_shows_due_date_with_year(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user, next_due_date=date(2027, 1, 15))
        response = authenticated_client.get("/recurring")
        assert "Jan 15, 2027" in response.text

    def test_card_shows_personal_badge(self, authenticated_client, test_user, uow):
        with uow:
            partner = uow.users.save(
                oidc_sub="card_partner@test.com",
                email="card_partner@test.com",
                display_name="Card Partner",
            )
        self._add_definition(
            uow, test_user,
            split_type=SplitType.PERCENTAGE,
            split_config={test_user.id: "100", partner.id: "0"},
        )
        response = authenticated_client.get("/recurring")
        assert "personal" in response.text

    def test_card_shows_auto_badge(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user, auto_generate=True)
        response = authenticated_client.get("/recurring")
        assert "auto" in response.text

    def test_card_footer_shows_category(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user, category="insurance")
        response = authenticated_client.get("/recurring")
        assert "insurance" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
mise run test -- tests/web/recurring_test.py::TestCardContent -v
```
Expected: `test_card_shows_due_date_with_year` FAILS (current template uses `"%b %-d"` — no year). Others may pass already.

- [ ] **Step 3: Rewrite `app/templates/recurring/_definition_card.html`**

```html
<!-- Recurring definition card — uses precomputed view model fields only, no business logic -->
{# defn is a RecurringDefinitionViewModel #}
<div id="definition-card-{{ defn.id }}"
     class="bg-white rounded-lg border border-stone-200 overflow-hidden mb-2 {% if not defn.is_active %}opacity-60{% endif %}"
     style="border-left: 4px solid {{ defn.category_border_color }}">

  <div class="px-4 pt-3 pb-2">
    <div class="flex items-start justify-between gap-3">

      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <h3 class="font-semibold text-stone-800 truncate text-sm">{{ defn.name }}</h3>
          {% if defn.is_auto_generate %}
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">auto</span>
          {% endif %}
          {% if defn.is_personal %}
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-pink-100 text-pink-700">personal</span>
          {% endif %}
          {% if not defn.is_active %}
            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-stone-100 text-stone-500">paused</span>
          {% endif %}
        </div>

        <p class="text-xs text-stone-600 mb-1">
          {{ defn.currency | currency_symbol }}{{ defn.amount | format_decimal }} / {{ defn.frequency_label }}
          ·
          <span class="inline-flex items-center gap-1">
            <span class="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 text-xs font-medium flex items-center justify-center"
                  title="{{ defn.payer_display_name }}">{{ defn.payer_initials }}</span>
            pays
          </span>
          · {{ defn.split_type }}
        </p>

        {% if defn.split_pills | length > 1 and not defn.is_even_split %}
          <div class="flex gap-1 mt-1 mb-1">
            {% for pill in defn.split_pills %}
              <span class="text-xs bg-stone-100 rounded px-1.5 py-0.5 text-stone-600">
                {{ pill.initials }}: {{ defn.currency | currency_symbol }}{{ pill.cost | format_decimal }}/mo
              </span>
            {% endfor %}
          </div>
        {% endif %}

        <p class="text-xs text-stone-400 mt-1">Due: {{ defn.next_due_date_display }}</p>
      </div>

      <div class="text-right shrink-0">
        <span class="text-sm font-bold text-indigo-600">
          {{ defn.currency | currency_symbol }}{{ defn.normalized_monthly_cost | format_decimal }}/mo
        </span>
        {% if defn.is_even_split and defn.split_pills %}
          <p class="text-xs text-stone-400">
            {{ defn.currency | currency_symbol }}{{ defn.split_pills[0].cost | format_decimal }}/person
          </p>
        {% elif defn.is_personal %}
          <p class="text-xs text-stone-400">{{ defn.split_pills[0].initials }} only</p>
        {% endif %}
      </div>

    </div>
  </div>

  <div class="px-4 py-1.5 bg-stone-50 border-t border-stone-100 flex items-center justify-between">
    <span class="text-xs text-stone-400">{{ defn.category if defn.category else "—" }}</span>
    <div class="flex items-center gap-1">
      {% if defn.is_manual_mode and defn.is_active %}
        <button
          type="button"
          hx-post="/recurring/{{ defn.id }}/create-expense"
          hx-target="#definition-card-{{ defn.id }}"
          hx-swap="outerHTML"
          hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'
          class="text-xs px-2 py-0.5 rounded border border-indigo-200 text-indigo-600 hover:bg-indigo-50 transition-colors"
        >Create</button>
      {% endif %}
      <a href="/recurring/{{ defn.id }}/edit"
         class="text-xs px-2 py-0.5 rounded border border-stone-200 text-stone-600 hover:bg-stone-100 transition-colors">
        Edit
      </a>
      <button
        type="button"
        hx-patch="/recurring/{{ defn.id }}/toggle-active"
        hx-target="#definition-card-{{ defn.id }}"
        hx-swap="outerHTML"
        hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'
        class="text-xs px-2 py-0.5 rounded border border-stone-200 text-stone-600 hover:bg-stone-100 transition-colors"
      >{% if defn.is_active %}Pause{% else %}Resume{% endif %}</button>
      <button
        type="button"
        onclick="openDeleteModal('{{ defn.id }}', '{{ defn.name | e }}')"
        class="text-xs px-2 py-0.5 rounded border border-red-200 text-red-500 hover:bg-red-50 transition-colors"
      >Delete</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Run tests**

```bash
mise run test -- tests/web/recurring_test.py::TestCardContent -v
```
Expected: all PASSED.

- [ ] **Step 5: Run all recurring tests**

```bash
mise run test -- tests/web/recurring_test.py -v
```
Expected: all PASSED.

- [ ] **Step 6: Commit**

```bash
git add app/templates/recurring/_definition_card.html tests/web/recurring_test.py
git commit -m "feat: rewrite definition card with border color, badges, split pills, full due date"
```

---

## Task 5: Rewrite _summary_bar.html as stats grid

**Files:**
- Modify: `app/templates/recurring/_summary_bar.html`
- Modify: `tests/web/recurring_test.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/web/recurring_test.py`:

```python
class TestSummaryBarStatsGrid:
    """Test the stats grid summary bar rendered by compute_registry_stats."""

    def _add_definition(self, uow, user, amount="20.00", split_type=SplitType.EVEN, split_config=None):
        row = RecurringDefinitionRow(
            name="Test Cost",
            amount=Decimal(amount),
            frequency=RecurringFrequency.MONTHLY,
            next_due_date=date(2026, 4, 1),
            payer_id=user.id,
            split_type=split_type,
            split_config=split_config,
            auto_generate=False,
            is_active=True,
            currency="EUR",
        )
        uow.session.add(row)
        uow.session.flush()

    def test_summary_shows_shared_label(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user)
        response = authenticated_client.get("/recurring")
        assert "Shared" in response.text

    def test_summary_shows_personal_label(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user)
        response = authenticated_client.get("/recurring")
        assert "Personal" in response.text

    def test_summary_shows_total_label(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user)
        response = authenticated_client.get("/recurring")
        assert "Total" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
mise run test -- tests/web/recurring_test.py::TestSummaryBarStatsGrid -v
```
Expected: `test_summary_shows_shared_label`, `test_summary_shows_personal_label`, `test_summary_shows_total_label` FAIL (current bar has none of these labels).

- [ ] **Step 3: Rewrite `app/templates/recurring/_summary_bar.html`**

```html
<!-- Summary stats grid — data from compute_registry_stats -->
{% if summary.has_active_definitions %}
<div class="grid grid-cols-3 gap-4 bg-stone-50 border border-stone-200 rounded-lg px-4 py-3 mb-4">

  <div class="flex flex-col">
    <span class="text-xs font-medium text-stone-400 uppercase tracking-wide mb-1">Shared /mo</span>
    <span class="text-base font-bold text-stone-800">
      {{ summary.currency | currency_symbol if summary.currency else "" }}{{ summary.shared_monthly_total | format_decimal }}
    </span>
    {% if summary.member_stats %}
      <span class="text-xs text-stone-500 mt-0.5">
        {% for m in summary.member_stats %}{{ m.initials }}: {{ summary.currency | currency_symbol if summary.currency else "" }}{{ m.shared_cost | format_decimal }}{% if not loop.last %} · {% endif %}{% endfor %}
      </span>
    {% endif %}
  </div>

  <div class="flex flex-col">
    <span class="text-xs font-medium text-stone-400 uppercase tracking-wide mb-1">Personal /mo</span>
    <span class="text-base font-bold text-stone-800">
      {{ summary.currency | currency_symbol if summary.currency else "" }}{{ summary.personal_monthly_totals.values() | sum | string | format_decimal if summary.personal_monthly_totals else "0.00" }}
    </span>
    {% if summary.member_stats %}
      <span class="text-xs text-stone-500 mt-0.5">
        {% for m in summary.member_stats %}{{ m.initials }}: {{ summary.currency | currency_symbol if summary.currency else "" }}{{ m.personal_cost | format_decimal }}{% if not loop.last %} · {% endif %}{% endfor %}
      </span>
    {% endif %}
  </div>

  <div class="flex flex-col">
    <span class="text-xs font-medium text-stone-400 uppercase tracking-wide mb-1">Total /mo</span>
    <span class="text-base font-bold text-stone-800">
      {{ summary.currency | currency_symbol if summary.currency else "" }}{{ summary.total_monthly_cost | format_decimal }}
    </span>
    <span class="text-xs text-stone-500 mt-0.5">{{ summary.active_count }} cost{{ summary.active_plural }}</span>
  </div>

</div>
{% endif %}
```

Note: The `currency` key is not currently in `compute_registry_stats`. Add it by reading from settings inside the function, or pass it via the route context. The simplest fix: add `"currency": settings.DEFAULT_CURRENCY` to the dict returned by `compute_registry_stats`. Add to the function in `view_models.py`:

```python
from app.settings import settings
# At the end of compute_registry_stats, add to the returned dict:
"currency": settings.DEFAULT_CURRENCY,
```

- [ ] **Step 4: Run tests**

```bash
mise run test -- tests/web/recurring_test.py::TestSummaryBarStatsGrid -v
```
Expected: all PASSED.

- [ ] **Step 5: Run all recurring tests**

```bash
mise run test -- tests/web/recurring_test.py -v
```
Expected: all PASSED.

- [ ] **Step 6: Commit**

```bash
git add app/templates/recurring/_summary_bar.html app/web/view_models.py tests/web/recurring_test.py
git commit -m "feat: rewrite summary bar as stats grid with shared/personal/total breakdown"
```

---

## Task 6: Filter chips in index and definition list

**Files:**
- Modify: `app/templates/recurring/index.html`
- Modify: `app/templates/recurring/_definition_list.html`
- Modify: `tests/web/recurring_test.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/web/recurring_test.py`:

```python
class TestFilterChips:
    """Test filter chips are rendered and include dynamic categories."""

    def _add_definition(self, uow, user, category=None):
        row = RecurringDefinitionRow(
            name="Test",
            amount=Decimal("10.00"),
            frequency=RecurringFrequency.MONTHLY,
            next_due_date=date(2026, 4, 1),
            payer_id=user.id,
            split_type=SplitType.EVEN,
            auto_generate=False,
            is_active=True,
            currency="EUR",
            category=category,
        )
        uow.session.add(row)
        uow.session.flush()

    def test_scope_chips_always_shown(self, authenticated_client):
        response = authenticated_client.get("/recurring")
        assert "Shared" in response.text
        assert "Personal" in response.text

    def test_category_chip_shown_for_active_category(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user, category="insurance")
        response = authenticated_client.get("/recurring")
        # insurance chip should appear
        assert "insurance" in response.text.lower()

    def test_category_chip_not_shown_for_absent_category(self, authenticated_client, test_user, uow):
        self._add_definition(uow, test_user, category="insurance")
        response = authenticated_client.get("/recurring")
        # membership was not added — its chip should not appear as a filter
        assert 'category=membership' not in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
mise run test -- tests/web/recurring_test.py::TestFilterChips -v
```
Expected: `test_scope_chips_always_shown` FAILS (no filter chips in current template).

- [ ] **Step 3: Add filter chips partial**

Create `app/templates/recurring/_filter_chips.html`:

```html
<!-- Filter chips — scope (All/Shared/Personal), payer chips, category chips -->
{# active_categories: list[str] passed from route; members: list[UserPublic] from request context #}
<div class="flex flex-wrap gap-2 mb-4" id="filter-chips">

  {# Scope chips #}
  <button
    class="text-xs px-3 py-1 rounded-full border border-stone-300 bg-white text-stone-600 hover:bg-stone-50 transition-colors font-medium"
    hx-get="/recurring/filtered?scope=all"
    hx-target="#definition-list"
    hx-swap="innerHTML"
  >All</button>

  <button
    class="text-xs px-3 py-1 rounded-full border border-stone-300 bg-white text-stone-600 hover:bg-stone-50 transition-colors font-medium"
    hx-get="/recurring/filtered?scope=shared"
    hx-target="#definition-list"
    hx-swap="innerHTML"
  >Shared</button>

  <button
    class="text-xs px-3 py-1 rounded-full border border-pink-300 bg-white text-pink-600 hover:bg-pink-50 transition-colors font-medium"
    hx-get="/recurring/filtered?scope=personal"
    hx-target="#definition-list"
    hx-swap="innerHTML"
  >Personal</button>

  {# Category chips — only for categories that have at least one active definition #}
  {% for cat in active_categories %}
    <button
      class="text-xs px-3 py-1 rounded-full border border-indigo-200 bg-white text-indigo-600 hover:bg-indigo-50 transition-colors font-medium capitalize"
      hx-get="/recurring/filtered?category={{ cat }}"
      hx-target="#definition-list"
      hx-swap="innerHTML"
    >{{ cat }}</button>
  {% endfor %}

</div>
```

- [ ] **Step 4: Add chips to `index.html`**

In `app/templates/recurring/index.html`, add the chips include just before `<div id="definition-list">`:

```html
  <!-- Filter chips -->
  {% include "recurring/_filter_chips.html" %}

  <!-- Definition list (swappable via HTMX) -->
  <div id="definition-list">
```

- [ ] **Step 5: Add chips to `_definition_list.html`**

Prepend the chips include so they're re-rendered on HTMX tab/filter swaps:

```html
<!-- Definition list partial — swapped by HTMX tab switching and filter endpoint -->
{% include "recurring/_filter_chips.html" %}
{% if definitions %}
  {% include "recurring/_summary_bar.html" %}
  <div class="space-y-3">
    {% for defn in definitions %}
      {% include "recurring/_definition_card.html" %}
    {% endfor %}
  </div>
{% else %}
  {% include "recurring/_empty_state.html" %}
{% endif %}
```

- [ ] **Step 6: Remove the chips include from `index.html`**

Since chips are now in `_definition_list.html`, remove the duplicate from `index.html`. The `index.html` div becomes:

```html
  <!-- Definition list (swappable via HTMX) -->
  <div id="definition-list">
    {% if definitions %}
      {% include "recurring/_summary_bar.html" %}
      ...
```

Wait — on initial page load, `index.html` renders the card list inline (not via partial). On HTMX swap, `_definition_list.html` is used. To avoid duplicating chips in both templates, include the chips ONLY in `_definition_list.html` and change `index.html` to also use the partial:

Replace the `#definition-list` section in `index.html` with:

```html
  <!-- Definition list (swappable via HTMX tab switching and filters) -->
  <div id="definition-list">
    {% include "recurring/_definition_list.html" %}
  </div>
```

This unifies the rendering path. The `_definition_list.html` partial now renders chips + summary + cards for both initial load and HTMX swaps.

- [ ] **Step 7: Run tests**

```bash
mise run test -- tests/web/recurring_test.py::TestFilterChips -v
```
Expected: all PASSED.

- [ ] **Step 8: Run all recurring tests**

```bash
mise run test -- tests/web/recurring_test.py -v
```
Expected: all PASSED.

- [ ] **Step 9: Commit**

```bash
git add app/templates/recurring/ tests/web/recurring_test.py
git commit -m "feat: add filter chips for scope, payer, and category to recurring page"
```

---

## Task 7: "Make Personal" toggle in the recurring form

**Files:**
- Modify: `app/templates/recurring/form.html`
- Modify: `app/web/recurring.py` — add `is_personal_edit` to form route contexts
- Modify: `tests/web/recurring_test.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/web/recurring_test.py`:

```python
class TestMakePersonalToggle:
    """Test the Make Personal toggle in the recurring form."""

    def test_form_shows_make_personal_button(self, authenticated_client):
        response = authenticated_client.get("/recurring/new")
        assert "Make Personal" in response.text

    def test_edit_form_pre_activates_toggle_for_personal_definition(
        self, authenticated_client, test_user, uow
    ):
        with uow:
            partner = uow.users.save(
                oidc_sub="personal_toggle@test.com",
                email="personal_toggle@test.com",
                display_name="Partner Toggle",
            )
        row = RecurringDefinitionRow(
            name="Gym",
            amount=Decimal("35.00"),
            frequency=RecurringFrequency.MONTHLY,
            next_due_date=date(2026, 5, 1),
            payer_id=test_user.id,
            split_type=SplitType.PERCENTAGE,
            split_config={test_user.id: "100", partner.id: "0"},
            auto_generate=False,
            is_active=True,
            currency="EUR",
        )
        uow.session.add(row)
        uow.session.flush()

        response = authenticated_client.get(f"/recurring/{row.id}/edit")
        assert response.status_code == 200
        # When editing a personal definition, the toggle state hint is in the page
        assert "is_personal_edit" in response.text or "Undo" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
mise run test -- tests/web/recurring_test.py::TestMakePersonalToggle -v
```
Expected: `test_form_shows_make_personal_button` FAILS (button not yet in template).

- [ ] **Step 3: Add `is_personal_edit` to `edit_recurring_form` route in `app/web/recurring.py`**

In `edit_recurring_form`, compute and pass `is_personal_edit`:

```python
is_personal_edit = (
    definition.split_type != SplitType.EVEN
    and definition.split_config is not None
    and any(Decimal(str(v)) == 0 for v in definition.split_config.values())
)
```

Add `"is_personal_edit": is_personal_edit` to the `TemplateResponse` context.

Also add `"is_personal_edit": False` to the `new_recurring_form` context, and both error re-render contexts in `create_recurring` and `update_recurring`.

Add `from decimal import Decimal` is already imported; this uses it directly in the route.

- [ ] **Step 4: Add "Make Personal" toggle to `form.html`**

Add the following block in `app/templates/recurring/form.html`, just before the split method `<div>` section (search for the split section heading):

```html
    <!-- Make Personal toggle -->
    <div class="mb-2">
      <button
        type="button"
        id="make-personal-btn"
        onclick="toggleMakePersonal()"
        class="px-4 py-2 text-sm rounded-lg border transition-colors {% if is_personal_edit %}border-pink-400 bg-pink-50 text-pink-700{% else %}border-stone-300 bg-white text-stone-700 hover:bg-stone-50{% endif %}"
      >
        {% if is_personal_edit %}Undo — make shared{% else %}Make Personal{% endif %}
      </button>
      <p class="text-xs text-stone-500 mt-1">One click to assign 100% of the cost to yourself.</p>
    </div>
```

Then add a `<script>` block at the end of the form's `{% block content %}`, before `{% endblock %}`:

```html
<script>
(function () {
  // IDs injected server-side for the JS toggle
  var currentUserId = {{ user.id }};
  var memberIds = [{% for m in members %}{{ m.id }}{% if not loop.last %},{% endif %}{% endfor %}];
  var partnerId = memberIds.find(function(id) { return id !== currentUserId; });

  var isPersonal = {{ 'true' if is_personal_edit else 'false' }};

  function setPersonalState(personal) {
    isPersonal = personal;
    var btn = document.getElementById('make-personal-btn');
    var splitSection = document.getElementById('split-fields-section');
    var splitTypeSelect = document.getElementById('split_type');
    var splitConfigInput = document.getElementById('split_config');
    var payerSelect = document.getElementById('payer_id');

    if (personal) {
      btn.textContent = 'Undo \u2014 make shared';
      btn.className = btn.className.replace('border-stone-300 bg-white text-stone-700 hover:bg-stone-50', 'border-pink-400 bg-pink-50 text-pink-700');
      if (splitSection) splitSection.style.display = 'none';
      if (splitTypeSelect) splitTypeSelect.value = 'PERCENTAGE';
      var config = {};
      config[currentUserId] = '100';
      if (partnerId) config[partnerId] = '0';
      if (splitConfigInput) splitConfigInput.value = JSON.stringify(config);
      if (payerSelect) payerSelect.value = String(currentUserId);
    } else {
      btn.textContent = 'Make Personal';
      btn.className = btn.className.replace('border-pink-400 bg-pink-50 text-pink-700', 'border-stone-300 bg-white text-stone-700 hover:bg-stone-50');
      if (splitSection) splitSection.style.display = '';
      if (splitTypeSelect) splitTypeSelect.value = 'EVEN';
      if (splitConfigInput) splitConfigInput.value = '';
    }
  }

  window.toggleMakePersonal = function () {
    setPersonalState(!isPersonal);
  };

  // Apply initial state on page load for edit mode
  if (isPersonal) {
    setPersonalState(true);
  }
})();
</script>
```

Also wrap the split fields section with `id="split-fields-section"` — find the split method div in the form and add the id attribute:

```html
<div id="split-fields-section">
  <!-- existing split type + split config fields -->
</div>
```

- [ ] **Step 5: Run tests**

```bash
mise run test -- tests/web/recurring_test.py::TestMakePersonalToggle -v
```
Expected: all PASSED.

- [ ] **Step 6: Run all tests**

```bash
mise run test -v
```
Expected: all PASSED.

- [ ] **Step 7: Run lint**

```bash
mise run lint:fix && mise run lint
```

- [ ] **Step 8: Commit**

```bash
git add app/templates/recurring/form.html app/web/recurring.py tests/web/recurring_test.py
git commit -m "feat: add Make Personal toggle to recurring form with JS state management"
```

---

## Self-Review

Spec section coverage:

| Spec Section | Task | Status |
|---|---|---|
| Section 1: View model (is_personal, personal_owner_id, per_person_monthly_cost) | Task 1 | ✓ |
| Section 1: get_registry_summary extended | Task 2 (compute_registry_stats) | ✓ |
| Section 2: /recurring/filtered endpoint | Task 3 | ✓ |
| Section 3: Card template rewrite | Task 4 | ✓ |
| Section 4: Summary bar stats grid | Task 5 | ✓ |
| Section 5: Filter chips | Task 6 | ✓ |
| Section 6: Make Personal toggle | Task 7 | ✓ |

**Potential issues resolved in plan:**
- `_to_view_models` calls `get_all_users` once; `compute_registry_stats` receives `member_names` — no duplicate queries.
- `active_categories` computed from full unfiltered active list in all routes (index, tab, filtered) so chip bar doesn't change as filters are applied.
- `_definition_list.html` includes filter chips so they re-render on every HTMX swap.
- The "personal" detection in `recurring_queries.py` (`_is_personal_domain`) and in `view_models.py` (`_detect_personal`) are separate but identical in logic — both check one zero and one nonzero value in split_config. Acceptable duplication across layers (query layer vs view layer).
