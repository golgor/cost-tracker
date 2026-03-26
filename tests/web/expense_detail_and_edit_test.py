"""Tests for expense detail and edit routes."""

from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import GroupRow, MembershipRow
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.models import ExpenseStatus, MemberRole, SplitType
from app.main import app


@pytest.fixture
def user1(uow: UnitOfWork):
    """Create first test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user1@test.com",
            email="user1@test.com",
            display_name="User One",
            actor_id=1,
        )
    return user


@pytest.fixture
def user2(uow: UnitOfWork):
    """Create second test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user2@test.com",
            email="user2@test.com",
            display_name="User Two",
            actor_id=2,
        )
    return user


@pytest.fixture
def test_group(user1, user2, uow: UnitOfWork):
    """Create a test group with two members."""
    group = GroupRow(
        name="Test Household",
        singleton_guard=True,
        default_currency="EUR",
        default_split_type=SplitType.EVEN,
    )
    uow.session.add(group)
    uow.session.flush()

    uow.session.add(MembershipRow(group_id=group.id, user_id=user1.id, role=MemberRole.ADMIN))
    uow.session.add(MembershipRow(group_id=group.id, user_id=user2.id, role=MemberRole.USER))
    uow.session.commit()

    return group


@pytest.fixture
def test_expense(user1, user2, test_group, uow: UnitOfWork):
    """Create a test expense."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Test expense",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
        )
    return expense


@pytest.fixture
def authenticated_client(user1, test_group, uow):
    """Test client with session cookie for user1."""
    app.dependency_overrides[get_uow] = lambda: uow

    client = TestClient(app, raise_server_exceptions=False)
    session_token = encode_session(user1.id)
    client.cookies.set("cost_tracker_session", session_token)

    yield client
    app.dependency_overrides.clear()


class TestExpenseDetailView:
    """Test expense detail expand/collapse functionality."""

    def test_expense_detail_loads_with_full_info(self, authenticated_client, test_expense, user1):
        """Test detail view shows all expense information."""
        response = authenticated_client.get(f"/expenses/{test_expense.id}/detail")

        assert response.status_code == 200
        assert "Test expense" in response.text
        assert "50.00" in response.text
        assert "User One" in response.text  # Creator
        assert "Split (Even)" in response.text
        assert "Edit Expense" in response.text  # Edit button visible for unsettled

    def test_expense_detail_shows_creator_and_payer_distinctly(
        self, authenticated_client, test_expense
    ):
        """Test FR8, FR42: Creator and payer displayed distinctly."""
        response = authenticated_client.get(f"/expenses/{test_expense.id}/detail")

        assert response.status_code == 200
        assert "Created by" in response.text
        assert "Paid by" in response.text

    def test_expense_collapse_returns_to_card_view(self, authenticated_client, test_expense):
        """Test collapse returns simple card view."""
        response = authenticated_client.get(f"/expenses/{test_expense.id}/collapse")

        assert response.status_code == 200
        # Should not have detail section with all the extra info
        assert "Created by" not in response.text
        assert "Split (Even)" not in response.text

    def test_settled_expense_shows_no_edit_button(self, authenticated_client, test_expense, uow):
        """Test settled expenses show read-only indicator."""
        # Mark expense as settled
        from app.adapters.sqlalchemy.orm_models import ExpenseRow

        with uow:
            row = uow.session.get(ExpenseRow, test_expense.id)
            assert row is not None
            row.status = ExpenseStatus.SETTLED
            uow.session.add(row)
            uow.session.commit()

        response = authenticated_client.get(f"/expenses/{test_expense.id}/detail")

        assert response.status_code == 200
        assert "Settled (Immutable)" in response.text
        assert "Edit Expense" not in response.text


class TestExpenseEditPage:
    """Test expense edit page and update functionality."""

    def test_edit_page_loads_with_expense_data(self, authenticated_client, test_expense):
        """Test edit page pre-populates form with expense data."""
        response = authenticated_client.get(f"/expenses/{test_expense.id}/edit")

        assert response.status_code == 200
        assert "Edit Expense" in response.text
        assert str(test_expense.amount) in response.text
        assert test_expense.description in response.text

    def test_edit_form_submission_updates_expense(self, authenticated_client, test_expense, uow):
        """Test form submission updates expense successfully."""
        # Get CSRF token
        get_response = authenticated_client.get(f"/expenses/{test_expense.id}/edit")
        csrf_token = get_response.cookies.get("csrf_token")

        response = authenticated_client.post(
            f"/expenses/{test_expense.id}/update",
            data={
                "amount": "123.45",
                "description": "Updated via form",
                "date": "2026-03-15",
                "payer_id": test_expense.payer_id,
                "currency": "EUR",
                "_csrf_token": csrf_token,
            },
            follow_redirects=False,
        )

        assert response.status_code == 303  # Redirect
        assert response.headers["location"] == "/expenses?updated=true"

        # Verify update persisted
        updated = uow.expenses.get_by_id(test_expense.id)
        assert updated.amount == Decimal("123.45")
        assert updated.description == "Updated via form"

    def test_edit_form_validation_errors_preserve_data(self, authenticated_client, test_expense):
        """Test validation errors preserve form data (UX-DR24)."""
        # Get CSRF token
        get_response = authenticated_client.get(f"/expenses/{test_expense.id}/edit")
        csrf_token = get_response.cookies.get("csrf_token")

        response = authenticated_client.post(
            f"/expenses/{test_expense.id}/update",
            data={
                "amount": "-50.00",  # Invalid: negative amount
                "description": "Test",
                "date": "2026-03-15",
                "payer_id": test_expense.payer_id,
                "currency": "EUR",
                "_csrf_token": csrf_token,
            },
        )

        assert response.status_code == 400
        assert (
            "Amount must be greater than zero" in response.text or "greater than 0" in response.text
        )
        # Form should preserve data
        assert "Test" in response.text

    def test_cannot_edit_settled_expense_via_form(self, authenticated_client, test_expense, uow):
        """Test settled expense edit returns error (FR7, FR20)."""
        # Mark expense as settled
        from app.adapters.sqlalchemy.orm_models import ExpenseRow

        with uow:
            row = uow.session.get(ExpenseRow, test_expense.id)
            assert row is not None
            row.status = ExpenseStatus.SETTLED
            uow.session.add(row)
            uow.session.commit()

        response = authenticated_client.post(
            f"/expenses/{test_expense.id}/update",
            data={
                "amount": "100.00",
                "description": "Attempt to edit settled",
                "date": "2026-03-15",
                "payer_id": test_expense.payer_id,
                "currency": "EUR",
            },
        )

        assert response.status_code == 403

    def test_settled_expense_edit_page_shows_warning(self, authenticated_client, test_expense, uow):
        """Test settled expense edit page shows warning banner."""
        # Mark expense as settled
        from app.adapters.sqlalchemy.orm_models import ExpenseRow

        with uow:
            row = uow.session.get(ExpenseRow, test_expense.id)
            assert row is not None
            row.status = ExpenseStatus.SETTLED
            uow.session.add(row)
            uow.session.commit()

        response = authenticated_client.get(f"/expenses/{test_expense.id}/edit")

        assert response.status_code == 200
        assert "settled and cannot be edited" in response.text
        # No save button should be present
        assert "Save Changes" not in response.text
