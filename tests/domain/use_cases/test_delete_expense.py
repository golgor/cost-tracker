"""Tests for expense deletion use case."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.errors import CannotEditSettledExpenseError, DomainError
from app.domain.models import ExpenseStatus
from app.domain.use_cases.expenses import create_expense, delete_expense
from tests.conftest import create_test_expense, create_test_group, create_test_user


def test_delete_expense_success(session_factory, uow_factory):
    """Test successful deletion of an unsettled expense."""
    # Setup
    session = session_factory()
    uow = uow_factory(session)

    user1 = create_test_user(session, oidc_sub="user1@test", email="user1@test.com")
    group = create_test_group(session, user1.id)

    # Create an expense
    with uow:
        expense = create_expense(
            uow=uow,
            group_id=group.id,
            amount=Decimal("50.00"),
            description="Test expense",
            creator_id=user1.id,
            payer_id=user1.id,
            date=date(2026, 3, 15),
            member_ids=[user1.id],
        )
        expense_id = expense.id

    # Verify expense exists
    assert uow.expenses.get_by_id(expense_id) is not None

    # Delete the expense
    with uow:
        delete_expense(
            uow=uow,
            expense_id=expense_id,
            actor_id=user1.id,
        )

    # Verify expense is deleted
    assert uow.expenses.get_by_id(expense_id) is None


def test_delete_expense_not_found(session_factory, uow_factory):
    """Test deletion of non-existent expense raises error."""
    session = session_factory()
    uow = uow_factory(session)

    user1 = create_test_user(session, oidc_sub="user1@test", email="user1@test.com")

    # Attempt to delete non-existent expense
    with pytest.raises(DomainError, match="Expense 99999 not found"), uow:
        delete_expense(
            uow=uow,
            expense_id=99999,
            actor_id=user1.id,
        )


def test_delete_settled_expense_fails(session_factory, uow_factory):
    """Test deletion of settled expense is blocked (immutability)."""
    # Setup
    session = session_factory()
    uow = uow_factory(session)

    user1 = create_test_user(session, oidc_sub="user1@test", email="user1@test.com")
    group = create_test_group(session, user1.id)

    # Create a settled expense directly
    expense = create_test_expense(
        session=session,
        group_id=group.id,
        amount=Decimal("100.00"),
        creator_id=user1.id,
        payer_id=user1.id,
        status=ExpenseStatus.SETTLED,
    )
    expense_id = expense.id

    # Attempt to delete settled expense
    with pytest.raises(CannotEditSettledExpenseError), uow:
        delete_expense(
            uow=uow,
            expense_id=expense_id,
            actor_id=user1.id,
        )

    # Verify expense still exists
    assert uow.expenses.get_by_id(expense_id) is not None


def test_delete_expense_audit_logging(session_factory, uow_factory):
    """Test that expense deletion creates audit log entry with snapshot."""
    from sqlalchemy import select

    from app.adapters.sqlalchemy.orm_models import AuditRow

    # Setup
    session = session_factory()
    uow = uow_factory(session)

    user1 = create_test_user(session, oidc_sub="user1@test", email="user1@test.com")
    group = create_test_group(session, user1.id)

    # Create an expense
    with uow:
        expense = create_expense(
            uow=uow,
            group_id=group.id,
            amount=Decimal("75.50"),
            description="Grocery shopping",
            creator_id=user1.id,
            payer_id=user1.id,
            date=date(2026, 3, 18),
            member_ids=[user1.id],
        )
        expense_id = expense.id

    # Delete the expense
    with uow:
        delete_expense(
            uow=uow,
            expense_id=expense_id,
            actor_id=user1.id,
        )

    # Verify audit log entry exists
    stmt = select(AuditRow).where(
        AuditRow.entity_type == "expense",
        AuditRow.entity_id == expense_id,
        AuditRow.action == "expense_deleted",
    )
    audit_logs = session.exec(stmt).all()

    assert len(audit_logs) == 1
    log = audit_logs[0]
    assert log.actor_id == user1.id
    assert log.changes is not None

    # Verify pre-deletion snapshot captured (old values, new is None)
    changes = log.changes
    assert "amount" in changes
    assert changes["amount"]["old"] == "75.50"
    assert changes["amount"]["new"] is None
    assert changes["description"]["old"] == "Grocery shopping"
    assert changes["description"]["new"] is None
