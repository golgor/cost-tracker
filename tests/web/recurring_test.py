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
        assert "1 active cost" in response.text

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
