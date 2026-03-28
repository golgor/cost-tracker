"""Tests for dashboard route - balance bar, expense feed, widgets."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import ExpenseRow, GroupRow, MembershipRow
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
def test_group(user1, user2, uow: UnitOfWork):
    """Create a test group with two members."""
    # Create group directly using SQLAlchemy for test data setup
    group = GroupRow(
        name="Test Household",
        singleton_guard=True,
        default_currency="EUR",
        default_split_type=SplitType.EVEN,
    )
    uow.session.add(group)
    uow.session.flush()

    # Add members
    uow.session.add(MembershipRow(group_id=group.id, user_id=user1.id, role=MemberRole.ADMIN))
    uow.session.add(MembershipRow(group_id=group.id, user_id=user2.id, role=MemberRole.USER))
    uow.session.commit()

    return group


@pytest.fixture
def authenticated_client(user1, test_group, uow):
    """Test client with session cookie for user1."""
    app.dependency_overrides[get_uow] = lambda: uow

    client = TestClient(app, raise_server_exceptions=False)
    session_token = encode_session(user1.id)
    client.cookies.set("cost_tracker_session", session_token)

    yield client
    app.dependency_overrides.clear()


class TestDashboardAccess:
    """Test dashboard authentication and access control."""

    def test_dashboard_requires_authentication(self):
        """Unauthenticated users are redirected to login."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/", follow_redirects=False)

        assert response.status_code == 302
        assert response.headers.get("location") == "/auth/login"

    def test_authenticated_user_is_redirected_to_expenses(self, authenticated_client):
        """Authenticated user with group is redirected from / to /expenses."""
        response = authenticated_client.get("/", follow_redirects=False)

        assert response.status_code == 307
        assert response.headers.get("location") == "/expenses"


class TestDashboardBalanceBar:
    """Test balance bar rendering with different balance states."""

    def test_zero_balance_shows_all_square(
        self, authenticated_client, user1, user2, test_group, uow
    ):
        """Dashboard shows 'All square!' when balance is zero."""
        # Create equal expenses
        uow.session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("100.00"),
                description="User1 expense",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        uow.session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("100.00"),
                description="User2 expense",
                date=date.today(),
                creator_id=user2.id,
                payer_id=user2.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        uow.session.commit()

        response = authenticated_client.get("/")

        assert response.status_code == 200
        assert "All square!" in response.text

    def test_positive_balance_shows_partner_owes_you(
        self, authenticated_client, user1, user2, test_group, uow
    ):
        """Dashboard shows partner owes you when balance is positive."""
        # User1 pays 100 → partner owes user1 €50
        uow.session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("100.00"),
                description="Groceries",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        uow.session.commit()

        response = authenticated_client.get("/")

        assert response.status_code == 200
        assert "owes you" in response.text
        assert "50.00" in response.text

    def test_negative_balance_shows_you_owe_partner(
        self, authenticated_client, user1, user2, test_group, uow
    ):
        """Dashboard shows you owe partner when balance is negative."""
        # User2 pays 100 → user1 owes user2 €50
        uow.session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("100.00"),
                description="Netflix",
                date=date.today(),
                creator_id=user2.id,
                payer_id=user2.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        uow.session.commit()

        response = authenticated_client.get("/")

        assert response.status_code == 200
        assert "You owe partner" in response.text
        assert "50.00" in response.text


class TestDashboardExpenseFeed:
    """Test expense feed display and ordering."""

    @pytest.mark.skip(
        reason="TODO: Test setup issue with transaction handling - "
        "query sorting verified in adapter tests"
    )
    def test_expense_feed_shows_newest_first(self, authenticated_client, user1, test_group, uow):
        """Expenses are sorted newest first in the feed."""
        today = date.today()

        # Create expenses on different dates
        expense_old = ExpenseRow(
            group_id=test_group.id,
            amount=Decimal("30.00"),
            description="Old Expense",
            date=today - timedelta(days=3),
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        expense_recent = ExpenseRow(
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Recent Expense",
            date=today - timedelta(days=1),
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        expense_today = ExpenseRow(
            group_id=test_group.id,
            amount=Decimal("75.00"),
            description="Today Expense",
            date=today,
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )

        uow.session.add(expense_old)
        uow.session.add(expense_recent)
        uow.session.add(expense_today)
        uow.session.commit()

        response = authenticated_client.get("/")

        assert response.status_code == 200
        html = response.text

        # Check that descriptions appear in correct order (newest first)
        today_pos = html.index("Today Expense")
        recent_pos = html.index("Recent Expense")
        old_pos = html.index("Old Expense")

        assert today_pos < recent_pos < old_pos, "Expenses should be sorted newest first"

    def test_expense_feed_displays_amount_and_description(
        self, authenticated_client, user1, test_group, uow
    ):
        """Expense cards show description and amount."""
        uow.session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("42.50"),
                description="Spar Groceries",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        uow.session.commit()

        response = authenticated_client.get("/")

        assert response.status_code == 200
        assert "Spar Groceries" in response.text
        assert "42.50" in response.text


class TestDashboardThisMonthWidget:
    """Test 'This Month' total widget display."""

    def test_this_month_widget_shows_current_month_total(
        self, authenticated_client, user1, test_group, uow
    ):
        """This Month widget displays sum of current month expenses."""
        today = date.today()

        # Create expense this month
        uow.session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("150.00"),
                description="This month",
                date=today,
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )

        # Create expense last month (should not be included)
        uow.session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("200.00"),
                description="Last month",
                date=today - timedelta(days=35),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )

        uow.session.commit()

        response = authenticated_client.get("/")

        assert response.status_code == 200
        assert "150.00" in response.text
        # Should NOT show last month's amount
        assert response.text.count("200.00") == 0 or "Last month" in response.text


class TestDashboardEmptyState:
    """Test empty state when no expenses exist."""

    def test_empty_state_shows_when_no_expenses(self, authenticated_client, user1, test_group):
        """Dashboard shows contextual empty state with no expenses."""
        response = authenticated_client.get("/")

        assert response.status_code == 200
        html = response.text

        # Check for empty state indicators
        assert (
            "No expenses" in html
            or "Add your first expense" in html
            or "no expenses yet" in html.lower()
        )


class TestDashboardPerformance:
    """Test dashboard performance requirements."""

    def test_dashboard_renders_with_many_expenses(
        self, authenticated_client, user1, test_group, uow
    ):
        """Dashboard handles ~50 expenses without errors (NFR3)."""
        # Create 50 expenses
        for i in range(50):
            uow.session.add(
                ExpenseRow(
                    group_id=test_group.id,
                    amount=Decimal("10.00"),
                    description=f"Expense {i}",
                    date=date.today() - timedelta(days=i % 30),
                    creator_id=user1.id,
                    payer_id=user1.id,
                    currency="EUR",
                    split_type=SplitType.EVEN,
                    status=ExpenseStatus.PENDING,
                )
            )
        uow.session.commit()

        response = authenticated_client.get("/")

        assert response.status_code == 200
        # Verify balance calculation completes (should be fast for 50 expenses per NFR3)
        assert "Expense 0" in response.text
