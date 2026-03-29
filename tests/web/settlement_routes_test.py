"""Tests for settlement web routes."""

from datetime import date
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    UserRow,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.models import ExpenseStatus, SplitType
from app.main import app


@pytest.fixture
def user1(uow: UnitOfWork):
    """Create first test user using direct SQLAlchemy."""
    user = UserRow(
        oidc_sub="user1@test.com",
        email="user1@test.com",
        display_name="Alice",
    )
    uow.session.add(user)
    uow.session.flush()
    return user


@pytest.fixture
def user2(uow: UnitOfWork):
    """Create second test user using direct SQLAlchemy."""
    user = UserRow(
        oidc_sub="user2@test.com",
        email="user2@test.com",
        display_name="Bob",
    )
    uow.session.add(user)
    uow.session.flush()
    return user


@pytest.fixture
def test_expense(user1, user2, uow: UnitOfWork):
    """Create a test expense directly via SQLAlchemy."""
    expense = ExpenseRow(
        amount=Decimal("100.00"),
        description="Test expense",
        date=date.today(),
        creator_id=user1.id,
        payer_id=user1.id,
        currency="EUR",
        split_type=SplitType.EVEN,
        status=ExpenseStatus.PENDING,
    )
    uow.session.add(expense)
    uow.session.flush()
    return expense


@pytest.fixture
def authenticated_client(user1, uow):
    """Test client with session cookie for user1."""
    app.dependency_overrides[get_uow] = lambda: uow

    client = TestClient(app, raise_server_exceptions=False)
    session_token = encode_session(user1.id)
    client.cookies.set("cost_tracker_session", session_token)

    yield client
    app.dependency_overrides.clear()


class TestSettlementReviewPage:
    """Tests for settlement review page."""

    def test_review_page_loads_with_unsettled_expenses(
        self, authenticated_client, user1, test_expense
    ):
        """Test review page shows unsettled expenses."""
        response = authenticated_client.get("/settlements/review")

        assert response.status_code == 200
        assert b"Review Expenses for Settlement" in response.content
        assert b"Test expense" in response.content

    def test_review_page_empty_state(self, authenticated_client, user1):
        """Test review page shows empty state when no unsettled expenses."""
        response = authenticated_client.get("/settlements/review")

        assert response.status_code == 200
        assert b"Nothing to settle" in response.content


class TestCalculateTotalEndpoint:
    """Tests for HTMX calculate total endpoint."""

    def test_calculate_total_htmx(self, authenticated_client, user1, test_expense):
        """Test HTMX endpoint returns updated total."""
        # Get CSRF token from review page
        get_response = authenticated_client.get("/settlements/review")
        csrf_token = get_response.cookies.get("csrf_token")

        response = authenticated_client.post(
            "/settlements/calculate-total",
            data={
                "expense_ids": str(test_expense.id),
                "_csrf_token": csrf_token,
            },
        )

        assert response.status_code == 200

    def test_calculate_total_no_selection(self, authenticated_client, user1):
        """Test HTMX endpoint with no selection."""
        # Get CSRF token from review page
        get_response = authenticated_client.get("/settlements/review")
        csrf_token = get_response.cookies.get("csrf_token")

        response = authenticated_client.post(
            "/settlements/calculate-total",
            data={"_csrf_token": csrf_token},
        )

        assert response.status_code == 200


class TestConfirmPage:
    """Tests for settlement confirmation page."""

    def test_confirm_page_loads(self, authenticated_client, user1, test_expense):
        """Test confirm page with selected expenses."""
        review_response = authenticated_client.get("/settlements/review")
        csrf_token = review_response.cookies.get("csrf_token")
        response = authenticated_client.post(
            "/settlements/confirm",
            data=f"expense_ids={test_expense.id}&_csrf_token={csrf_token}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        assert response.status_code == 200
        assert b"Confirm Settlement" in response.content

    def test_confirm_page_validation_no_expenses(self, authenticated_client, user1):
        """Test confirm page redirects when no expenses selected."""
        csrf_token = authenticated_client.get("/settlements/review").cookies.get("csrf_token")
        response = authenticated_client.post(
            "/settlements/confirm",
            data={"_csrf_token": csrf_token},
            follow_redirects=False,
        )

        assert response.status_code == 303  # Redirect


class TestCreateSettlement:
    """Tests for settlement creation endpoint."""

    def test_create_settlement_success(self, authenticated_client, uow, user1, test_expense):
        """Test creating a settlement marks expenses as settled."""
        # Get CSRF token from review page
        get_response = authenticated_client.get("/settlements/review")
        csrf_token = get_response.cookies.get("csrf_token")

        response = authenticated_client.post(
            "/settlements",
            data={
                "expense_ids": str(test_expense.id),
                "_csrf_token": csrf_token,
            },
            follow_redirects=False,
        )

        assert response.status_code == 303  # Redirect to success

        # Verify expense is now settled
        with uow:
            expense = uow.expenses.get_by_id(test_expense.id)
            assert expense.status == ExpenseStatus.SETTLED


class TestSettlementHistory:
    """Tests for settlement history page."""

    def test_history_page_empty_state(self, authenticated_client, user1):
        """Test history page shows empty state."""
        response = authenticated_client.get("/settlements")

        assert response.status_code == 200
        assert (
            b"No settlements yet" in response.content or b"Settlement History" in response.content
        )


class TestSettlementDetail:
    """Tests for settlement detail page."""

    def test_detail_page_requires_authentication(self):
        """Unauthenticated users are redirected to login."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/settlements/1", follow_redirects=False)

        assert response.status_code == 302
        assert response.headers.get("location") == "/auth/login"

    def test_detail_page_not_found(self, authenticated_client, user1):
        """Test detail page returns 404 for non-existent settlement."""
        response = authenticated_client.get("/settlements/99999")

        assert response.status_code == 404
