"""Tests for /api/v1/expenses CRUD endpoints."""

import pytest
from starlette.testclient import TestClient

from tests.conftest import create_test_expense, create_test_user


@pytest.fixture
def api_client(db_session):
    from app.api.v1.auth import verify_api_key
    from app.api.v1.router import api_v1
    from app.dependencies import get_db_session

    api_v1.dependency_overrides[get_db_session] = lambda: db_session
    api_v1.dependency_overrides[verify_api_key] = lambda: None
    client = TestClient(api_v1)
    yield client
    api_v1.dependency_overrides.clear()


@pytest.fixture
def two_users(db_session):
    user1 = create_test_user(
        db_session, oidc_sub="sub1", email="alice@example.com", display_name="Alice"
    )
    user2 = create_test_user(
        db_session, oidc_sub="sub2", email="bob@example.com", display_name="Bob"
    )
    db_session.flush()
    return user1, user2


class TestGetExpenses:
    def test_list_returns_200(self, api_client, two_users):
        response = api_client.get("/expenses")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_returns_existing_expenses(self, api_client, db_session, two_users):
        user1, user2 = two_users
        create_test_expense(db_session, amount="50.00", creator_id=user1.id, payer_id=user1.id)
        db_session.flush()

        response = api_client.get("/expenses")
        data = response.json()
        assert len(data) >= 1
        assert data[0]["amount"] == "50.00"

    def test_get_by_id_returns_200(self, api_client, db_session, two_users):
        user1, _ = two_users
        expense = create_test_expense(
            db_session, amount="30.00", creator_id=user1.id, payer_id=user1.id
        )
        db_session.flush()

        response = api_client.get(f"/expenses/{expense.id}")
        assert response.status_code == 200
        assert response.json()["id"] == expense.id

    def test_get_by_id_returns_404_for_missing(self, api_client):
        response = api_client.get("/expenses/999999")
        assert response.status_code == 404


class TestCreateExpense:
    def test_create_returns_201(self, api_client, two_users):
        user1, user2 = two_users
        payload = {
            "amount": "42.00",
            "description": "Spar",
            "creator_id": user1.id,
            "payer_id": user1.id,
            "member_ids": [user1.id, user2.id],
            "currency": "EUR",
            "split_type": "EVEN",
        }
        response = api_client.post("/expenses", json=payload)
        assert response.status_code == 201

    def test_create_returns_expense_data(self, api_client, two_users):
        user1, user2 = two_users
        payload = {
            "amount": "100.00",
            "description": "Ikea",
            "creator_id": user1.id,
            "payer_id": user1.id,
            "member_ids": [user1.id, user2.id],
            "currency": "EUR",
            "split_type": "EVEN",
        }
        response = api_client.post("/expenses", json=payload)
        data = response.json()
        assert data["description"] == "Ikea"
        assert data["amount"] == "100.00"
        assert "id" in data

    def test_create_with_date(self, api_client, two_users):
        user1, user2 = two_users
        payload = {
            "amount": "55.00",
            "description": "OMV",
            "date": "2025-07-06",
            "creator_id": user1.id,
            "payer_id": user1.id,
            "member_ids": [user1.id, user2.id],
            "currency": "EUR",
        }
        response = api_client.post("/expenses", json=payload)
        assert response.status_code == 201
        assert response.json()["date"] == "2025-07-06"

    def test_create_with_invalid_split_type_returns_422(self, api_client, two_users):
        user1, user2 = two_users
        payload = {
            "amount": "50.00",
            "description": "Bad",
            "creator_id": user1.id,
            "payer_id": user1.id,
            "member_ids": [user1.id, user2.id],
            "currency": "EUR",
            "split_type": "NOT_A_VALID_TYPE",
        }
        response = api_client.post("/expenses", json=payload)
        assert response.status_code == 422

    def test_create_shares_split_without_config_returns_domain_error(self, api_client, two_users):
        user1, user2 = two_users
        payload = {
            "amount": "50.00",
            "description": "Bad",
            "creator_id": user1.id,
            "payer_id": user1.id,
            "member_ids": [user1.id, user2.id],
            "currency": "EUR",
            "split_type": "SHARES",
            # Missing split_config for SHARES type
        }
        response = api_client.post("/expenses", json=payload)
        # InvalidShareError is a DomainError → handled by api_v1 domain_error_handler → 422
        assert response.status_code == 422


class TestUpdateExpense:
    def test_update_returns_204(self, api_client, db_session, two_users):
        user1, _ = two_users
        expense = create_test_expense(
            db_session, amount="40.00", creator_id=user1.id, payer_id=user1.id
        )
        db_session.flush()

        response = api_client.put(f"/expenses/{expense.id}", json={"amount": "45.00"})
        assert response.status_code == 204

    def test_update_nonexistent_returns_404(self, api_client):
        response = api_client.put("/expenses/999999", json={"amount": "10.00"})
        assert response.status_code == 404

    def test_update_settled_expense_returns_403(self, api_client, db_session, two_users):
        user1, _ = two_users
        expense = create_test_expense(
            db_session, amount="40.00", creator_id=user1.id, payer_id=user1.id, status="SETTLED"
        )
        db_session.flush()

        response = api_client.put(f"/expenses/{expense.id}", json={"amount": "45.00"})
        # CannotEditSettledExpenseError maps to 403 in _API_ERROR_MAP
        assert response.status_code == 403
