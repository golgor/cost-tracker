"""Tests for expense deletion use case."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.errors import CannotEditSettledExpenseError, DomainError
from app.domain.use_cases.expenses import create_expense, delete_expense
from tests.conftest import create_test_expense, create_test_user


def test_delete_expense_success(uow):
    """Test successful deletion of an unsettled expense."""
    user1 = create_test_user(uow.session, oidc_sub="user1@test", email="user1@test.com")

    # Create an expense
    with uow:
        expense = create_expense(
            uow=uow,
            amount=Decimal("50.00"),
            description="Test expense",
            creator_id=user1.id,
            payer_id=user1.id,
            date=date(2026, 3, 15),
            member_ids=[user1.id],
            currency="EUR",
        )
        expense_id = expense.id

    # Verify expense exists
    assert uow.expenses.get_by_id(expense_id) is not None

    # Delete the expense
    with uow:
        delete_expense(
            uow=uow,
            expense_id=expense_id,
        )

    # Verify expense is deleted
    assert uow.expenses.get_by_id(expense_id) is None


def test_delete_expense_not_found(uow):
    """Test deletion of non-existent expense raises error."""
    create_test_user(uow.session, oidc_sub="user1@test", email="user1@test.com")

    # Attempt to delete non-existent expense
    with pytest.raises(DomainError, match="Expense 99999 not found"), uow:
        delete_expense(
            uow=uow,
            expense_id=99999,
        )


def test_delete_settled_expense_fails(uow):
    """Test deletion of settled expense is blocked (immutability)."""
    user1 = create_test_user(uow.session, oidc_sub="user1@test", email="user1@test.com")

    # Create a settled expense directly
    expense = create_test_expense(
        session=uow.session,
        amount="100.00",
        creator_id=user1.id,
        payer_id=user1.id,
        status="SETTLED",
    )
    expense_id = expense.id

    # Attempt to delete settled expense
    with pytest.raises(CannotEditSettledExpenseError), uow:
        delete_expense(
            uow=uow,
            expense_id=expense_id,
        )

    # Verify expense still exists
    assert uow.expenses.get_by_id(expense_id) is not None
