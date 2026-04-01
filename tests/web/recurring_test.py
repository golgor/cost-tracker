"""Tests for recurring definitions registry route."""

from datetime import date
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import RecurringDefinitionRow
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.models import RecurringFrequency, SplitType
from app.main import app


@pytest.fixture
def test_user(uow: UnitOfWork):
    """Create a test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="recurring_user@test.com",
            email="recurring_user@test.com",
            display_name="Recurring User",
        )
    return user


@pytest.fixture
def authenticated_client(test_user, uow):
    """Test client authenticated as test_user."""
    app.dependency_overrides[get_uow] = lambda: uow
    client = TestClient(app, raise_server_exceptions=False)
    session_token = encode_session(test_user.id)
    client.cookies.set("cost_tracker_session", session_token)
    yield client
    app.dependency_overrides.clear()


class TestRecurringRegistryAccess:
    """Test authentication and basic access to the registry."""

    def test_registry_requires_authentication(self):
        """Unauthenticated users are redirected to login."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/recurring", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers.get("location") == "/auth/login"

    def test_registry_returns_200_for_authenticated_user(self, authenticated_client):
        """Authenticated user gets 200 on registry page."""
        response = authenticated_client.get("/recurring")
        assert response.status_code == 200

    def test_registry_renders_page_title(self, authenticated_client):
        """Registry page contains 'Recurring Costs' heading."""
        response = authenticated_client.get("/recurring")
        assert "Recurring Costs" in response.text

    def test_registry_shows_add_button(self, authenticated_client):
        """Registry page shows '+ Add Recurring' button."""
        response = authenticated_client.get("/recurring")
        assert "Add Recurring" in response.text


class TestRecurringRegistryEmptyState:
    """Test empty state rendering when no definitions exist."""

    def test_empty_state_shown_with_no_definitions(self, authenticated_client):
        """Registry shows empty state message when no definitions exist."""
        response = authenticated_client.get("/recurring")
        assert response.status_code == 200
        assert "No recurring costs yet" in response.text

    def test_empty_state_shows_add_button(self, authenticated_client):
        """Empty state has an Add Recurring Cost button."""
        response = authenticated_client.get("/recurring")
        assert "Add Recurring Cost" in response.text


class TestRecurringRegistryWithDefinitions:
    """Test registry rendering with existing definitions."""

    def _add_definition(self, uow, user, name="Netflix", amount="14.99"):
        row = RecurringDefinitionRow(
            name=name,
            amount=Decimal(amount),
            frequency=RecurringFrequency.MONTHLY,
            next_due_date=date(2026, 4, 1),
            payer_id=user.id,
            split_type=SplitType.EVEN,
            auto_generate=False,
            is_active=True,
            currency="EUR",
        )
        uow.session.add(row)
        uow.session.commit()
        return row

    def test_definition_name_appears_in_registry(self, authenticated_client, test_user, uow):
        """Definition name appears in the registry page."""
        self._add_definition(uow, test_user, name="Netflix")
        response = authenticated_client.get("/recurring")
        assert response.status_code == 200
        assert "Netflix" in response.text

    def test_summary_bar_shows_count(self, authenticated_client, test_user, uow):
        """Summary bar shows active count when definitions exist."""
        self._add_definition(uow, test_user, name="Spotify")
        response = authenticated_client.get("/recurring")
        assert "1 cost" in response.text

    def test_normalized_monthly_cost_shown(self, authenticated_client, test_user, uow):
        """Definition card shows the normalized monthly cost."""
        self._add_definition(uow, test_user, amount="14.99")
        response = authenticated_client.get("/recurring")
        assert "14.99" in response.text

    def test_tabs_are_present(self, authenticated_client):
        """Registry page renders Active and Paused tabs."""
        response = authenticated_client.get("/recurring")
        assert "Active" in response.text
        assert "Paused" in response.text

    def test_paused_tab_htmx_endpoint(self, authenticated_client, test_user, uow):
        """HTMX tab endpoint returns 200 for 'paused' tab."""
        response = authenticated_client.get(
            "/recurring/tab/paused",
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200

    def test_active_tab_htmx_endpoint(self, authenticated_client, test_user, uow):
        """HTMX tab endpoint returns 200 for 'active' tab."""
        response = authenticated_client.get(
            "/recurring/tab/active",
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200

    def test_invalid_tab_returns_400(self, authenticated_client):
        """HTMX tab endpoint returns 400 for unknown tab name."""
        response = authenticated_client.get("/recurring/tab/unknown")
        assert response.status_code == 400

    def test_paused_definitions_not_in_active_tab(self, authenticated_client, test_user, uow):
        """Paused definitions do not appear in the Active tab."""
        paused = RecurringDefinitionRow(
            name="Paused Service",
            amount=Decimal("9.99"),
            frequency=RecurringFrequency.MONTHLY,
            next_due_date=date(2026, 4, 1),
            payer_id=test_user.id,
            split_type=SplitType.EVEN,
            auto_generate=False,
            is_active=False,  # paused
            currency="EUR",
        )
        uow.session.add(paused)
        uow.session.commit()

        response = authenticated_client.get("/recurring")
        # Active tab should not show paused service
        assert "Paused Service" not in response.text

    def test_paused_definitions_appear_in_paused_tab(self, authenticated_client, test_user, uow):
        """Paused definitions appear in the Paused tab HTMX response."""
        paused = RecurringDefinitionRow(
            name="Paused Service",
            amount=Decimal("9.99"),
            frequency=RecurringFrequency.MONTHLY,
            next_due_date=date(2026, 4, 1),
            payer_id=test_user.id,
            split_type=SplitType.EVEN,
            auto_generate=False,
            is_active=False,
            currency="EUR",
        )
        uow.session.add(paused)
        uow.session.commit()

        response = authenticated_client.get("/recurring/tab/paused")
        assert response.status_code == 200
        assert "Paused Service" in response.text


class TestRecurringForm:
    """Test the new and edit recurring definition form pages."""

    def test_new_form_requires_authentication(self):
        """Unauthenticated users are redirected to login."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/recurring/new", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers.get("location") == "/auth/login"

    def test_new_form_returns_200(self, authenticated_client):
        """Authenticated user gets 200 on the new form page."""
        response = authenticated_client.get("/recurring/new")
        assert response.status_code == 200

    def test_new_form_shows_user_in_payer_dropdown(self, authenticated_client, test_user):
        """The payer dropdown includes the current user's display name."""
        response = authenticated_client.get("/recurring/new")
        assert response.status_code == 200
        assert test_user.display_name in response.text

    def test_new_form_shows_all_users_in_payer_dropdown(self, authenticated_client, test_user, uow):
        """The payer dropdown includes all registered users."""
        with uow:
            second_user = uow.users.save(
                oidc_sub="second@test.com",
                email="second@test.com",
                display_name="Second User",
            )

        response = authenticated_client.get("/recurring/new")
        assert response.status_code == 200
        assert test_user.display_name in response.text
        assert second_user.display_name in response.text


class TestFilteredEndpoint:
    """Test the /recurring/filtered HTMX endpoint."""

    def _add_definition(
        self,
        uow,
        user,
        name: str = "Netflix",
        amount: str = "14.99",
        category: str | None = None,
        split_type: SplitType = SplitType.EVEN,
        split_config: dict | None = None,
    ):
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

    def test_filtered_scope_personal_shows_only_personal(
        self, authenticated_client, test_user, uow
    ):
        with uow:
            partner = uow.users.save(
                oidc_sub="filter_partner@test.com",
                email="filter_partner@test.com",
                display_name="Filter Partner",
            )
        self._add_definition(
            uow,
            test_user,
            name="Gym",
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
            uow,
            test_user,
            name="Personal Gym",
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
            uow,
            test_user,
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
            split_config=None,
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
        assert "category=insurance" in response.text

    def test_category_chip_not_shown_for_absent_category(
        self, authenticated_client, test_user, uow
    ):
        self._add_definition(uow, test_user, category="insurance")
        response = authenticated_client.get("/recurring")
        assert "category=membership" not in response.text


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
        # When editing a personal definition, the toggle renders "Undo — make shared"
        assert "Undo" in response.text


class TestSummaryBarStatsGrid:
    """Test the stats grid summary bar rendered by compute_registry_stats."""

    def _add_definition(
        self, uow, user, amount="20.00", split_type=SplitType.EVEN, split_config=None
    ):
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
