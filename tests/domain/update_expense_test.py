"""Tests for update expense use case."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.domain.errors import DomainError
from app.domain.models import ExpenseStatus
from app.domain.use_cases.expenses import CannotEditSettledExpenseError, update_expense


@pytest.fixture
def user1(uow):
    """Create first test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user1@test.com",
            email="user1@test.com",
            display_name="User One",
        )
    return user


@pytest.fixture
def user2(uow):
    """Create second test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user2@test.com",
            email="user2@test.com",
            display_name="User Two",
        )
    return user


@pytest.fixture
def test_group(user1, user2, uow):
    """Create a test group with both users as members."""
    with uow:
        group = uow.groups.save(name="Test Household")
        uow.groups.add_member(group.id, user1.id, "ADMIN")
        uow.groups.add_member(group.id, user2.id, "USER")
    return group


def test_update_expense_changes_amount(uow, test_group, user1, user2):
    """Test updating expense amount."""
    # Create an expense
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Original expense",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
        )

    # Update the amount
    with uow:
        update_expense(
            uow=uow,
            expense_id=expense.id,
            amount=Decimal("99.99"),
        )

    # Verify update
    with uow:
        updated = uow.expenses.get_by_id(expense.id)
        assert updated is not None
        assert updated.amount == Decimal("99.99")
        assert updated.description == "Original expense"  # Unchanged


def test_update_expense_changes_description(uow, test_group, user1, user2):
    """Test updating expense description."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Original",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
        )

    with uow:
        update_expense(
            uow=uow,
            expense_id=expense.id,
            description="Updated description",
        )

    with uow:
        updated = uow.expenses.get_by_id(expense.id)
        assert updated.description == "Updated description"


def test_update_expense_changes_payer(uow, test_group, user1, user2):
    """Test updating expense payer."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Test",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
        )

    with uow:
        update_expense(
            uow=uow,
            expense_id=expense.id,
            payer_id=user2.id,
        )

    with uow:
        updated = uow.expenses.get_by_id(expense.id)
        assert updated.payer_id == user2.id


def test_update_expense_changes_date(uow, test_group, user1, user2):
    """Test updating expense date."""
    from app.domain.use_cases.expenses import create_expense

    original_date = date.today() - timedelta(days=5)
    new_date = date.today() - timedelta(days=2)

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Test",
            creator_id=user1.id,
            payer_id=user1.id,
            date=original_date,
            member_ids=[user1.id, user2.id],
        )

    with uow:
        update_expense(
            uow=uow,
            expense_id=expense.id,
            date=new_date,
        )

    with uow:
        updated = uow.expenses.get_by_id(expense.id)
        assert updated.date == new_date


def test_cannot_edit_settled_expense(uow: UnitOfWork, test_group, user1, user2):
    """Test immutability: settled expenses cannot be edited (FR7, FR20)."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Test",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
        )

    # Manually mark expense as settled (settlement logic not implemented yet)
    from app.adapters.sqlalchemy.orm_models import ExpenseRow

    with uow:
        row = uow.session.get(ExpenseRow, expense.id)
        assert row is not None
        row.status = ExpenseStatus.SETTLED
        uow.session.add(row)
        uow.session.commit()

    # Attempt to update settled expense should raise error
    with pytest.raises(CannotEditSettledExpenseError) as exc_info, uow:
        update_expense(
            uow=uow,
            expense_id=expense.id,
            amount=Decimal("99.99"),
        )

    assert exc_info.value.expense_id == expense.id


def test_update_expense_validates_positive_amount(uow, test_group, user1, user2):
    """Test validation: amount must be positive."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Test",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
        )

    with pytest.raises(DomainError, match="Amount must be greater than zero"), uow:
        update_expense(
            uow=uow,
            expense_id=expense.id,
            amount=Decimal("-10.00"),
        )


def test_update_expense_validates_future_date(uow, test_group, user1, user2):
    """Test validation: date cannot be in the future."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Test",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
        )

    future_date = date.today() + timedelta(days=1)
    with pytest.raises(DomainError, match="cannot be in the future"), uow:
        update_expense(
            uow=uow,
            expense_id=expense.id,
            date=future_date,
        )


def test_update_expense_changes_multiple_fields(uow: UnitOfWork, test_group, user1, user2):
    """Test updating multiple fields at once."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("50.00"),
            description="Original",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
        )

    # Update multiple fields
    with uow:
        update_expense(
            uow=uow,
            expense_id=expense.id,
            amount=Decimal("75.00"),
            description="Updated",
        )

    # Verify both fields were updated
    with uow:
        updated = uow.expenses.get_by_id(expense.id)
        assert updated is not None
        assert updated.amount == Decimal("75.00")
        assert updated.description == "Updated"
