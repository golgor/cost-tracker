"""Tests for expenses list route and filtering functionality."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import ExpenseRow
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.models import ExpenseStatus, SplitType
from app.main import app


@pytest.fixture
def user1(uow: UnitOfWork):
    """Create first test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user1@test.com",
            email="user1@test.com",
            display_name="User One",
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
        )
    return user


@pytest.fixture
def authenticated_client(user1, user2, uow):
    """Test client with session cookie for user1."""
    app.dependency_overrides[get_uow] = lambda: uow

    client = TestClient(app, raise_server_exceptions=False)
    session_token = encode_session(user1.id)
    client.cookies.set("cost_tracker_session", session_token)

    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def expenses_list_setup(user1, user2, uow: UnitOfWork):
    """Set up test data for expenses list tests."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    last_week = today - timedelta(days=7)

    # Create expenses using ORM directly
    uow.session.add(
        ExpenseRow(
            amount=Decimal("25.50"),
            description="Groceries",
            date=today,
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
    )

    uow.session.add(
        ExpenseRow(
            amount=Decimal("100.00"),
            description="Electricity bill",
            date=yesterday,
            creator_id=user2.id,
            payer_id=user2.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
    )

    uow.session.add(
        ExpenseRow(
            amount=Decimal("45.75"),
            description="Restaurant",
            date=last_week,
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
    )
    uow.session.commit()

    return {
        "user1_id": user1.id,
        "user2_id": user2.id,
        "today": today,
        "yesterday": yesterday,
        "last_week": last_week,
    }


class TestExpensesListRoute:
    """Tests for GET /expenses route."""

    def test_get_expenses_returns_200(self, authenticated_client):
        """Test that GET /expenses returns 200 OK."""
        response = authenticated_client.get("/expenses")
        assert response.status_code == 200

    def test_get_expenses_with_no_expense_shows_empty_state(self, authenticated_client):
        """Test that expenses list with zero expenses shows contextual empty state."""
        response = authenticated_client.get("/expenses")
        assert response.status_code == 200
        assert "No expenses yet" in response.text or "No shared expenses" in response.text

    def test_get_expenses_shows_all_expenses_sorted_newest_first(
        self, authenticated_client, expenses_list_setup
    ):
        """Test that GET /expenses shows all expenses sorted by date descending."""
        response = authenticated_client.get("/expenses")
        assert response.status_code == 200

        # Check all expenses are present
        assert "Groceries" in response.text
        assert "Electricity bill" in response.text
        assert "Restaurant" in response.text

        # Check amounts are displayed
        assert "25.50" in response.text
        assert "100.00" in response.text
        assert "45.75" in response.text

        # Verify sorting order: newer expenses should appear before older ones
        groceries_pos = response.text.find("Groceries")
        electricity_pos = response.text.find("Electricity bill")
        restaurant_pos = response.text.find("Restaurant")

        # Newest first: Groceries (today) < Electricity (yesterday) < Restaurant (last week)
        assert groceries_pos < electricity_pos, (
            "Groceries (today) should appear before Electricity bill (yesterday)"
        )
        assert electricity_pos < restaurant_pos, (
            "Electricity bill (yesterday) should appear before Restaurant (last week)"
        )

    def test_get_expenses_shows_filter_bar(self, authenticated_client):
        """Test that expenses list displays filter bar UI."""
        response = authenticated_client.get("/expenses")
        assert response.status_code == 200

        # Check for filter controls
        assert "filter" in response.text.lower() or "Filter" in response.text

    def test_get_expenses_shows_desktop_sidebar_form(self, authenticated_client):
        """Test that desktop view includes the expense sidebar form."""
        response = authenticated_client.get("/expenses")
        assert response.status_code == 200

        # Check for desktop sidebar form presence
        assert "expense-sidebar" in response.text or "Add Expense" in response.text

    def test_expenses_navigation_item_exists(self, authenticated_client):
        """Test that 'Expenses' navigation item is accessible."""
        response = authenticated_client.get("/expenses")
        assert response.status_code == 200
        # Just verify the route works; actual nav item rendering tested in template tests


class TestExpensesFilterRoute:
    """Tests for expense filtering functionality."""

    def test_filter_by_date_range(self, authenticated_client, expenses_list_setup):
        """Test that filtering by date range works correctly."""
        # Filter to only show today's expenses
        today_str = expenses_list_setup["today"].isoformat()
        response = authenticated_client.get(
            f"/expenses/filtered?date_from={today_str}&date_to={today_str}"
        )
        assert response.status_code == 200

        # Should show today's expense
        assert "Groceries" in response.text

        # Should not show older expenses
        assert "Electricity bill" not in response.text
        assert "Restaurant" not in response.text

    def test_filter_by_payer(self, authenticated_client, expenses_list_setup):
        """Test that filtering by payer_id works correctly."""
        user1_id = expenses_list_setup["user1_id"]
        response = authenticated_client.get(f"/expenses/filtered?payer_id={user1_id}")
        assert response.status_code == 200

        # Should show expenses paid by user1
        assert "Groceries" in response.text
        assert "Restaurant" in response.text

        # Should not show expenses paid by user2
        assert "Electricity bill" not in response.text

    def test_filter_combined_date_and_payer(self, authenticated_client, expenses_list_setup):
        """Test that combining date and payer filters works correctly."""
        user1_id = expenses_list_setup["user1_id"]
        last_week_str = expenses_list_setup["last_week"].isoformat()
        today_str = expenses_list_setup["today"].isoformat()

        response = authenticated_client.get(
            f"/expenses/filtered?date_from={last_week_str}&date_to={today_str}&payer_id={user1_id}"
        )
        assert response.status_code == 200

        # Should show user1's expenses
        assert "Groceries" in response.text
        assert "Restaurant" in response.text

    def test_filter_with_no_results_shows_empty_state(
        self, authenticated_client, expenses_list_setup
    ):
        """Test that filtering with no matching results shows contextual empty state."""
        # Use a date range from far future
        future_date = date.today() + timedelta(days=365)
        response = authenticated_client.get(
            f"/expenses/filtered?date_from={future_date.isoformat()}&date_to={future_date.isoformat()}"
        )
        assert response.status_code == 200

        # Should show empty state message
        assert "No expenses match" in response.text or "no results" in response.text.lower()


class TestExpenseResultCount:
    """Tests for expense result count display."""

    def test_result_count_displays_total_expenses(self, authenticated_client, expenses_list_setup):
        """Test that expense count displays correctly."""
        response = authenticated_client.get("/expenses")
        assert response.status_code == 200

        # Should display count (3 expenses created in fixture)
        assert "3 expense" in response.text or "3 Expense" in response.text

    def test_result_count_updates_with_filters(self, authenticated_client, expenses_list_setup):
        """Test that result count updates based on active filters."""
        user1_id = expenses_list_setup["user1_id"]
        response = authenticated_client.get(f"/expenses/filtered?payer_id={user1_id}")
        assert response.status_code == 200

        # Should display filtered count (user1 paid for 2 expenses)
        assert "2 expense" in response.text or "2 Expense" in response.text
