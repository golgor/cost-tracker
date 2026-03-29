"""Tests for recurring definition create/edit form routes."""

from datetime import date
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import GroupRow, MembershipRow, RecurringDefinitionRow
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.models import MemberRole, RecurringFrequency, SplitType
from app.main import app


@pytest.fixture
def test_user(uow: UnitOfWork):
    """Create a test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="form_user@test.com",
            email="form_user@test.com",
            display_name="Form User",
        )
    return user


@pytest.fixture
def test_group(test_user, uow: UnitOfWork):
    """Create a test group with the test user as admin."""
    group = GroupRow(
        name="Test Household",
        singleton_guard=True,
        default_currency="EUR",
        default_split_type=SplitType.EVEN,
    )
    uow.session.add(group)
    uow.session.flush()
    uow.session.add(MembershipRow(group_id=group.id, user_id=test_user.id, role=MemberRole.ADMIN))
    uow.session.commit()
    return group


@pytest.fixture
def authenticated_client(test_user, test_group, uow):
    """Test client authenticated as test_user."""
    app.dependency_overrides[get_uow] = lambda: uow
    client = TestClient(app, raise_server_exceptions=False)
    session_token = encode_session(test_user.id)
    client.cookies.set("cost_tracker_session", session_token)
    yield client
    app.dependency_overrides.clear()


def _add_definition(uow, group, user, name="Netflix", amount="14.99"):
    row = RecurringDefinitionRow(
        group_id=group.id,
        name=name,
        amount=Decimal(amount),
        frequency=RecurringFrequency.MONTHLY,
        next_due_date=date(2026, 5, 1),
        payer_id=user.id,
        split_type=SplitType.EVEN,
        auto_generate=False,
        is_active=True,
        currency="EUR",
    )
    uow.session.add(row)
    uow.session.commit()
    return row


class TestNewRecurringFormPage:
    """Tests for GET /recurring/new."""

    def test_requires_authentication(self):
        """Unauthenticated users are redirected to login."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/recurring/new", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers.get("location") == "/auth/login"

    def test_returns_200_for_authenticated_user(self, authenticated_client):
        """Authenticated user with group gets 200 on the new form page."""
        response = authenticated_client.get("/recurring/new")
        assert response.status_code == 200

    def test_form_contains_name_field(self, authenticated_client):
        """New form contains name input field."""
        response = authenticated_client.get("/recurring/new")
        assert 'name="name"' in response.text

    def test_form_contains_amount_field(self, authenticated_client):
        """New form contains amount input field."""
        response = authenticated_client.get("/recurring/new")
        assert 'name="amount"' in response.text

    def test_form_contains_frequency_options(self, authenticated_client):
        """New form contains frequency selector with expected options."""
        response = authenticated_client.get("/recurring/new")
        assert "Monthly" in response.text
        assert "Quarterly" in response.text
        assert "Every N Months" in response.text

    def test_form_contains_auto_generate_toggle(self, authenticated_client):
        """New form contains auto-generate checkbox."""
        response = authenticated_client.get("/recurring/new")
        assert 'name="auto_generate"' in response.text

    def test_form_shows_add_heading(self, authenticated_client):
        """New form shows 'Add Recurring Cost' heading."""
        response = authenticated_client.get("/recurring/new")
        assert "Add Recurring Cost" in response.text

    def test_no_edit_banner_on_create_form(self, authenticated_client):
        """Create form does not show the edit-forward info banner."""
        response = authenticated_client.get("/recurring/new")
        assert "Changes apply to future expenses only" not in response.text


class TestCreateRecurring:
    """Tests for POST /recurring."""

    def test_valid_submission_redirects_to_registry(self, authenticated_client, test_user):
        """Valid form submission redirects to /recurring."""
        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/recurring",
            data={
                "name": "Netflix",
                "amount": "14.99",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers.get("location") == "/recurring"

    def test_definition_persisted_after_create(
        self, authenticated_client, test_user, test_group, uow
    ):
        """After a valid POST, the definition exists in the database."""
        from sqlmodel import select

        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        authenticated_client.post(
            "/recurring",
            data={
                "name": "Spotify",
                "amount": "9.99",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
            follow_redirects=False,
        )

        rows = uow.session.exec(
            select(RecurringDefinitionRow).where(RecurringDefinitionRow.name == "Spotify")
        ).all()
        assert len(rows) == 1

    def test_missing_name_returns_422(self, authenticated_client, test_user):
        """Missing required name field returns validation error."""
        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/recurring",
            data={
                "name": "",
                "amount": "14.99",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
        )
        assert response.status_code in (400, 422)

    def test_invalid_amount_returns_form_with_error(self, authenticated_client, test_user):
        """Non-numeric amount returns the form with an error message."""
        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/recurring",
            data={
                "name": "Netflix",
                "amount": "abc",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
        )
        assert response.status_code == 422
        assert "Invalid amount" in response.text

    def test_zero_amount_returns_form_with_error(self, authenticated_client, test_user):
        """Zero amount returns the form with an error message."""
        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/recurring",
            data={
                "name": "Netflix",
                "amount": "0",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
        )
        assert response.status_code == 422
        assert "greater than zero" in response.text

    def test_every_n_months_without_interval_returns_error(self, authenticated_client, test_user):
        """EVERY_N_MONTHS without interval_months returns validation error."""
        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/recurring",
            data={
                "name": "Netflix",
                "amount": "14.99",
                "frequency": "EVERY_N_MONTHS",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
        )
        assert response.status_code == 422
        assert "Interval is required" in response.text

    def test_every_n_months_with_valid_interval_succeeds(self, authenticated_client, test_user):
        """EVERY_N_MONTHS with interval_months=3 redirects successfully."""
        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/recurring",
            data={
                "name": "Car Service",
                "amount": "300.00",
                "frequency": "EVERY_N_MONTHS",
                "interval_months": "3",
                "next_due_date": "2026-07-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "_csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    def test_form_data_preserved_on_error(self, authenticated_client, test_user):
        """Form re-renders with submitted values when validation fails."""
        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/recurring",
            data={
                "name": "My Service",
                "amount": "bad",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
        )
        assert "My Service" in response.text


class TestEditRecurringFormPage:
    """Tests for GET /recurring/{id}/edit."""

    def test_returns_200_for_existing_definition(
        self, authenticated_client, test_user, test_group, uow
    ):
        """Edit form page returns 200 for an existing definition."""
        row = _add_definition(uow, test_group, test_user, name="Spotify")
        response = authenticated_client.get(f"/recurring/{row.id}/edit")
        assert response.status_code == 200

    def test_form_pre_populated_with_existing_values(
        self, authenticated_client, test_user, test_group, uow
    ):
        """Edit form pre-populates fields with the definition's current values."""
        row = _add_definition(uow, test_group, test_user, name="Amazon Prime", amount="8.99")
        response = authenticated_client.get(f"/recurring/{row.id}/edit")
        assert "Amazon Prime" in response.text
        assert "8.99" in response.text

    def test_edit_banner_shown_in_edit_mode(self, authenticated_client, test_user, test_group, uow):
        """Edit form shows the edit-forward info banner."""
        row = _add_definition(uow, test_group, test_user)
        response = authenticated_client.get(f"/recurring/{row.id}/edit")
        assert "Changes apply to future expenses only" in response.text

    def test_returns_404_for_missing_definition(self, authenticated_client):
        """Edit form returns 404 for a non-existent definition ID."""
        response = authenticated_client.get("/recurring/99999/edit")
        assert response.status_code == 404

    def test_shows_save_changes_button(self, authenticated_client, test_user, test_group, uow):
        """Edit form shows 'Save Changes' submit button."""
        row = _add_definition(uow, test_group, test_user)
        response = authenticated_client.get(f"/recurring/{row.id}/edit")
        assert "Save Changes" in response.text


class TestUpdateRecurring:
    """Tests for POST /recurring/{id}."""

    def test_valid_update_redirects_to_registry(
        self, authenticated_client, test_user, test_group, uow
    ):
        """Valid update form submission redirects to /recurring."""
        row = _add_definition(uow, test_group, test_user, name="Netflix")
        csrf_token = authenticated_client.get(f"/recurring/{row.id}/edit").cookies.get("csrf_token")
        response = authenticated_client.post(
            f"/recurring/{row.id}",
            data={
                "name": "Netflix Premium",
                "amount": "17.99",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers.get("location") == "/recurring"

    def test_name_updated_in_database(self, authenticated_client, test_user, test_group, uow):
        """After valid update, the definition's name is changed in the database."""
        from sqlmodel import select

        row = _add_definition(uow, test_group, test_user, name="Netflix")
        csrf_token = authenticated_client.get(f"/recurring/{row.id}/edit").cookies.get("csrf_token")
        authenticated_client.post(
            f"/recurring/{row.id}",
            data={
                "name": "Netflix Premium",
                "amount": "17.99",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
            follow_redirects=False,
        )

        uow.session.expire_all()
        updated = uow.session.exec(
            select(RecurringDefinitionRow).where(RecurringDefinitionRow.id == row.id)
        ).first()
        assert updated is not None
        assert updated.name == "Netflix Premium"

    def test_invalid_amount_returns_422(self, authenticated_client, test_user, test_group, uow):
        """Invalid amount returns 422 with error message."""
        row = _add_definition(uow, test_group, test_user)
        csrf_token = authenticated_client.get(f"/recurring/{row.id}/edit").cookies.get("csrf_token")
        response = authenticated_client.post(
            f"/recurring/{row.id}",
            data={
                "name": "Netflix",
                "amount": "-5",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
        )
        assert response.status_code == 422

    def test_returns_404_for_missing_definition(self, authenticated_client, test_user):
        """Update returns 404 for a non-existent definition ID."""
        csrf_token = authenticated_client.get("/recurring/new").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/recurring/99999",
            data={
                "name": "X",
                "amount": "10.00",
                "frequency": "MONTHLY",
                "next_due_date": "2026-05-01",
                "payer_id": str(test_user.id),
                "split_type": "EVEN",
                "split_config": "",
                "category": "",
                "auto_generate": "",
                "interval_months": "",
                "_csrf_token": csrf_token,
            },
        )
        assert response.status_code == 404
