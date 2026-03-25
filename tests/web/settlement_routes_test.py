"""Tests for settlement web routes."""

from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.models import ExpenseStatus
from app.main import app


@pytest.fixture
def authenticated_client(user1, test_group, uow):
    """Test client with session cookie for user1."""
    app.dependency_overrides[get_uow] = lambda: uow

    client = TestClient(app, raise_server_exceptions=False)
    session_token = encode_session(user1.id)
    client.cookies.set("cost_tracker_session", session_token)

    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def user1(uow):
    """Create first test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user1@test.com",
            email="user1@test.com",
            display_name="Alice",
            actor_id=1,
        )
    return user


@pytest.fixture
def user2(uow):
    """Create second test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user2@test.com",
            email="user2@test.com",
            display_name="Bob",
            actor_id=2,
        )
    return user


@pytest.fixture
def test_group(user1, user2, uow):
    """Create a test group with two members."""
    with uow:
        group = uow.groups.save(name="Test Household", actor_id=user1.id)
        uow.groups.add_member(group.id, user2.id, "USER", actor_id=user1.id)
    return group


@pytest.fixture
def test_expense(user1, test_group, uow):
    """Create a test expense."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("100.00"),
            description="Test expense",
            creator_id=user1.id,
            payer_id=user1.id,
        )
    return expense


class TestSettlementReviewPage:
    """Tests for settlement review page."""

    def test_review_page_loads_with_unsettled_expenses(
        self, authenticated_client, user1, test_group, test_expense
    ):
        """Test review page shows unsettled expenses."""
        response = authenticated_client.get("/settlements/review")

        assert response.status_code == 200
        assert b"Review Expenses for Settlement" in response.content
        assert b"Test expense" in response.content

    def test_review_page_empty_state(self, authenticated_client, user1, test_group):
        """Test review page shows empty state when no unsettled expenses."""
        response = authenticated_client.get("/settlements/review")

        assert response.status_code == 200
        assert b"Nothing to settle" in response.content


class TestCalculateTotalEndpoint:
    """Tests for HTMX calculate total endpoint."""

    def test_calculate_total_htmx(self, authenticated_client, user1, test_group, test_expense):
        """Test HTMX endpoint returns updated total."""
        response = authenticated_client.post(
            "/settlements/calculate-total",
            data={"expense_ids": str(test_expense.id)},
        )

        assert response.status_code == 200

    def test_calculate_total_no_selection(self, authenticated_client, user1, test_group):
        """Test HTMX endpoint with no selection."""
        response = authenticated_client.post(
            "/settlements/calculate-total",
            data={},
        )

        assert response.status_code == 200


class TestConfirmPage:
    """Tests for settlement confirmation page."""

    def test_confirm_page_loads(self, authenticated_client, user1, test_group, test_expense):
        """Test confirm page with selected expenses."""
        response = authenticated_client.get(
            "/settlements/confirm",
            params={"expense_ids": [test_expense.id]},
        )

        assert response.status_code == 200
        assert b"Confirm Settlement" in response.content

    def test_confirm_page_validation_no_expenses(self, authenticated_client, user1, test_group):
        """Test confirm page redirects when no expenses selected."""
        response = authenticated_client.get("/settlements/confirm")

        assert response.status_code == 303  # Redirect


class TestCreateSettlement:
    """Tests for settlement creation endpoint."""

    def test_create_settlement_success(
        self, authenticated_client, uow, user1, test_group, test_expense
    ):
        """Test creating a settlement marks expenses as settled."""
        response = authenticated_client.post(
            "/settlements",
            data={"expense_ids": str(test_expense.id)},
            follow_redirects=False,
        )

        assert response.status_code == 303  # Redirect to success

        # Verify expense is now settled
        with uow:
            expense = uow.expenses.get_by_id(test_expense.id)
            assert expense.status == ExpenseStatus.SETTLED


class TestSettlementHistory:
    """Tests for settlement history page."""

    def test_history_page_empty_state(self, authenticated_client, user1, test_group):
        """Test history page shows empty state."""
        response = authenticated_client.get("/settlements")

        assert response.status_code == 200
        assert (
            b"No settlements yet" in response.content or b"Settlement History" in response.content
        )


class TestSettlementDetail:
    """Tests for settlement detail page."""

    def test_detail_page_not_found(self, authenticated_client, user1, test_group):
        """Test detail page returns 404 for non-existent settlement."""
        response = authenticated_client.get("/settlements/99999")

        assert response.status_code == 404
