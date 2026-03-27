"""Tests for keyword search in the expenses routes."""

import pytest
from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import ExpenseNoteRow, GroupRow, MembershipRow
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.models import MemberRole, SplitType
from app.main import app
from tests.conftest import create_test_expense


@pytest.fixture
def search_user(uow: UnitOfWork):
    with uow:
        user = uow.users.save(
            oidc_sub="search_web_user@test.com",
            email="search_web_user@test.com",
            display_name="Search User",
            actor_id=1,
        )
    return user


@pytest.fixture
def search_group(search_user, uow: UnitOfWork):
    group = GroupRow(
        name="Search Test Household",
        singleton_guard=True,
        default_currency="EUR",
        default_split_type=SplitType.EVEN,
    )
    uow.session.add(group)
    uow.session.flush()
    uow.session.add(MembershipRow(group_id=group.id, user_id=search_user.id, role=MemberRole.ADMIN))
    uow.session.commit()
    return group


@pytest.fixture
def search_expenses(search_user, search_group, uow: UnitOfWork):
    """Create expenses: one matching 'coffee', one matching a note keyword."""
    coffee = create_test_expense(
        uow.session,
        search_group.id,
        "4.50",
        search_user.id,
        search_user.id,
        description="Morning coffee",
    )
    grocery = create_test_expense(
        uow.session,
        search_group.id,
        "40.00",
        search_user.id,
        search_user.id,
        description="Weekly groceries",
    )
    uow.session.add(
        ExpenseNoteRow(
            expense_id=grocery.id,
            author_id=search_user.id,
            content="Bought at supermarket",
        )
    )
    uow.session.commit()
    return {"coffee": coffee, "grocery": grocery}


@pytest.fixture
def client(search_user, search_group, uow):
    app.dependency_overrides[get_uow] = lambda: uow
    tc = TestClient(app, raise_server_exceptions=False)
    tc.cookies.set("cost_tracker_session", encode_session(search_user.id))
    yield tc
    app.dependency_overrides.clear()


class TestExpenseSearchBar:
    def test_search_bar_is_present_on_expenses_page(self, client, search_expenses):
        response = client.get("/expenses")
        assert response.status_code == 200
        assert 'id="expense-search"' in response.text
        assert "Search expenses..." in response.text

    def test_search_query_preserved_in_input(self, client, search_expenses):
        response = client.get("/expenses?search_query=coffee")
        assert response.status_code == 200
        assert 'value="coffee"' in response.text


class TestExpensesFilteredWithSearch:
    def test_search_returns_matching_expense_by_description(self, client, search_expenses):
        response = client.get("/expenses/filtered?search_query=coffee")
        assert response.status_code == 200
        assert "Morning coffee" in response.text
        assert "Weekly groceries" not in response.text

    def test_search_returns_matching_expense_by_note(self, client, search_expenses):
        response = client.get("/expenses/filtered?search_query=supermarket")
        assert response.status_code == 200
        assert "Weekly groceries" in response.text
        assert "Morning coffee" not in response.text

    def test_search_case_insensitive(self, client, search_expenses):
        response = client.get("/expenses/filtered?search_query=COFFEE")
        assert response.status_code == 200
        assert "Morning coffee" in response.text

    def test_search_no_results_shows_empty_state(self, client, search_expenses):
        response = client.get("/expenses/filtered?search_query=zzznomatch")
        assert response.status_code == 200
        assert "No expenses match your search" in response.text

    def test_search_count_message_shown(self, client, search_expenses):
        response = client.get("/expenses/filtered?search_query=coffee")
        assert response.status_code == 200
        assert "result" in response.text.lower()

    def test_empty_search_returns_all_expenses(self, client, search_expenses):
        response = client.get("/expenses/filtered?search_query=")
        assert response.status_code == 200
        assert "Morning coffee" in response.text
        assert "Weekly groceries" in response.text

    def test_search_combined_with_payer_filter(self, client, search_expenses, search_user):
        # Both expenses are paid by search_user, so filtering by payer + search should work
        response = client.get(f"/expenses/filtered?search_query=coffee&payer_id={search_user.id}")
        assert response.status_code == 200
        assert "Morning coffee" in response.text
