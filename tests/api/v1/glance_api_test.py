"""Tests for the Glance Dashboard API endpoints."""

from datetime import date
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    ExpenseSplitRow,
    GroupRow,
    MembershipRow,
    RecurringDefinitionRow,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.api.v1.router import api_v1
from app.dependencies import get_db_session
from app.domain.models import (
    ExpenseStatus,
    MemberRole,
    RecurringFrequency,
    SplitType,
)
from app.main import app
from app.settings import settings

API_URL = "/api/v1/summary"
VALID_AUTH = f"Bearer {settings.GLANCE_API_KEY}"


@pytest.fixture
def user1(uow: UnitOfWork):
    with uow:
        return uow.users.save(
            oidc_sub="alice@test.com",
            email="alice@test.com",
            display_name="Alice",
            actor_id=1,
        )


@pytest.fixture
def user2(uow: UnitOfWork):
    with uow:
        return uow.users.save(
            oidc_sub="bob@test.com",
            email="bob@test.com",
            display_name="Bob",
            actor_id=2,
        )


@pytest.fixture
def test_group(user1, user2, uow: UnitOfWork):
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
def api_client(db_session):
    """Test client with db_session override (no session cookie needed — API key auth).

    Overrides on the sub-application (api_v1) since it's mounted as a separate
    ASGI app — the main app's dependency_overrides don't propagate to it.
    """
    api_v1.dependency_overrides[get_db_session] = lambda: db_session
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    api_v1.dependency_overrides.clear()


class TestApiAuthentication:
    """Test API key authentication."""

    def test_missing_auth_returns_403(self, api_client):
        response = api_client.get(API_URL)
        assert response.status_code == 403

    def test_invalid_auth_returns_403(self, api_client):
        response = api_client.get(API_URL, headers={"Authorization": "Bearer wrong-key"})
        assert response.status_code == 403

    def test_valid_auth_returns_200(self, api_client, test_group):
        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        assert response.status_code == 200


class TestSummaryEmptyState:
    """Test summary endpoint with no data."""

    def test_no_group_returns_empty_summary(self, api_client):
        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        assert response.status_code == 200

        data = response.json()
        assert data["month"]["total"] == "0.00"
        assert data["month"]["expense_count"] == 0
        assert data["month"]["unsettled_count"] == 0
        assert data["month"]["balance"]["direction"] == "All square"
        assert data["month"]["balance"]["members"] == []
        assert data["recurring"]["active_count"] == 0
        assert data["recurring"]["total_monthly_cost"] == "0.00"
        assert data["recurring"]["upcoming"] == []

    def test_group_no_expenses_returns_zeros(self, api_client, test_group):
        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        data = response.json()

        assert data["month"]["total"] == "0.00"
        assert data["month"]["expense_count"] == 0
        assert data["month"]["currency"] == "EUR"
        assert data["month"]["balance"]["net_amount"] == "0.00"
        assert data["month"]["balance"]["direction"] == "All square"
        assert len(data["month"]["balance"]["members"]) == 2


class TestSummaryWithExpenses:
    """Test summary endpoint with expense data."""

    def test_month_total_and_count(self, api_client, test_group, user1, user2, db_session):
        db_session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("50.00"),
                description="Groceries",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        db_session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("30.00"),
                description="Coffee",
                date=date.today(),
                creator_id=user2.id,
                payer_id=user2.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        db_session.flush()

        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        data = response.json()

        assert data["month"]["total"] == "80.00"
        assert data["month"]["expense_count"] == 2
        assert data["month"]["unsettled_count"] == 2

    def test_balance_with_splits(self, api_client, test_group, user1, user2, db_session):
        """Balance correctly reflects split amounts."""
        expense = ExpenseRow(
            group_id=test_group.id,
            amount=Decimal("100.00"),
            description="Dinner",
            date=date.today(),
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        db_session.add(expense)
        db_session.flush()

        # Add splits: Alice paid 100, split 50/50
        db_session.add(
            ExpenseSplitRow(expense_id=expense.id, user_id=user1.id, amount=Decimal("50.00"))
        )
        db_session.add(
            ExpenseSplitRow(expense_id=expense.id, user_id=user2.id, amount=Decimal("50.00"))
        )
        db_session.flush()

        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        data = response.json()

        balance = data["month"]["balance"]
        assert balance["net_amount"] == "50.00"
        assert "Bob" in balance["direction"]
        assert "Alice" in balance["direction"]
        assert len(balance["members"]) == 2

    def test_money_values_are_strings(self, api_client, test_group, user1, db_session):
        """All money values are serialized as strings, not floats."""
        db_session.add(
            ExpenseRow(
                group_id=test_group.id,
                amount=Decimal("99.99"),
                description="Test",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        db_session.flush()

        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        data = response.json()

        # Money values must be strings
        assert isinstance(data["month"]["total"], str)
        assert isinstance(data["month"]["balance"]["net_amount"], str)
        assert isinstance(data["recurring"]["total_monthly_cost"], str)


class TestSummaryWithRecurring:
    """Test summary endpoint with recurring definitions."""

    def test_recurring_summary(self, api_client, test_group, user1, db_session):
        db_session.add(
            RecurringDefinitionRow(
                group_id=test_group.id,
                name="Netflix",
                amount=Decimal("15.99"),
                frequency=RecurringFrequency.MONTHLY,
                next_due_date=date(2026, 4, 1),
                payer_id=user1.id,
                split_type=SplitType.EVEN,
                auto_generate=True,
                is_active=True,
                currency="EUR",
            )
        )
        db_session.add(
            RecurringDefinitionRow(
                group_id=test_group.id,
                name="Spotify",
                amount=Decimal("9.99"),
                frequency=RecurringFrequency.MONTHLY,
                next_due_date=date(2026, 4, 15),
                payer_id=user1.id,
                split_type=SplitType.EVEN,
                auto_generate=True,
                is_active=True,
                currency="EUR",
            )
        )
        db_session.flush()

        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        data = response.json()

        assert data["recurring"]["active_count"] == 2
        assert data["recurring"]["total_monthly_cost"] == "25.98"
        assert data["recurring"]["currency"] == "EUR"
        assert len(data["recurring"]["upcoming"]) == 2

        # First upcoming should be Netflix (earlier date)
        assert data["recurring"]["upcoming"][0]["name"] == "Netflix"
        assert data["recurring"]["upcoming"][0]["amount"] == "15.99"
        assert data["recurring"]["upcoming"][0]["next_due_date"] == "2026-04-01"
        assert data["recurring"]["upcoming"][0]["frequency"] == "monthly"
        assert data["recurring"]["upcoming"][0]["payer"] == "Alice"

    def test_limit_parameter(self, api_client, test_group, user1, db_session):
        """?limit= controls how many upcoming items are returned."""
        for i in range(5):
            db_session.add(
                RecurringDefinitionRow(
                    group_id=test_group.id,
                    name=f"Service {i}",
                    amount=Decimal("10.00"),
                    frequency=RecurringFrequency.MONTHLY,
                    next_due_date=date(2026, 4, i + 1),
                    payer_id=user1.id,
                    split_type=SplitType.EVEN,
                    auto_generate=True,
                    is_active=True,
                    currency="EUR",
                )
            )
        db_session.flush()

        response = api_client.get(f"{API_URL}?limit=2", headers={"Authorization": VALID_AUTH})
        data = response.json()

        assert data["recurring"]["active_count"] == 5
        assert len(data["recurring"]["upcoming"]) == 2

    def test_period_is_current_month(self, api_client, test_group):
        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        data = response.json()

        today = date.today()
        expected_period = f"{today.year}-{today.month:02d}"
        assert data["month"]["period"] == expected_period


class TestBalanceWithTodaysExpenses:
    """Regression test: expenses dated today must contribute to balance.

    Previously, a SQL join bug (session.exec with multi-entity select) caused
    today's expenses to be silently excluded from the balance calculation.
    """

    def test_balance_correct_with_today_expenses(
        self, api_client, test_group, user1, user2, db_session
    ):
        """Two expenses both dated today produce correct balance direction."""
        # Alice (user1) pays €50, Bob (user2) pays €30 — both today
        expense1 = ExpenseRow(
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Dinner",
            date=date.today(),
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        expense2 = ExpenseRow(
            group_id=test_group.id,
            amount=Decimal("30.00"),
            description="Coffee",
            date=date.today(),
            creator_id=user2.id,
            payer_id=user2.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        db_session.add(expense1)
        db_session.add(expense2)
        db_session.flush()

        # Add splits (even split: each person owes half)
        db_session.add(
            ExpenseSplitRow(expense_id=expense1.id, user_id=user1.id, amount=Decimal("25.00"))
        )
        db_session.add(
            ExpenseSplitRow(expense_id=expense1.id, user_id=user2.id, amount=Decimal("25.00"))
        )
        db_session.add(
            ExpenseSplitRow(expense_id=expense2.id, user_id=user1.id, amount=Decimal("15.00"))
        )
        db_session.add(
            ExpenseSplitRow(expense_id=expense2.id, user_id=user2.id, amount=Decimal("15.00"))
        )
        db_session.flush()

        response = api_client.get(API_URL, headers={"Authorization": VALID_AUTH})
        data = response.json()

        balance = data["month"]["balance"]
        # Alice paid €50 (owed €25), owes €15 for Bob's → net +€10
        # Bob paid €30 (owed €15), owes €25 for Alice's → net -€10
        assert balance["net_amount"] == "10.00"
        assert "Bob" in balance["direction"]
        assert "Alice" in balance["direction"]
        # Bob owes Alice
        assert balance["direction"] == "Bob owes Alice"
