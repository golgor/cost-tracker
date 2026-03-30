"""Tests for expense domain use cases."""

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from app.domain.models import ExpensePublic, ExpenseStatus, SplitType
from app.domain.use_cases.expenses import create_expense


def test_create_expense_success(mocker):
    """Test creating a valid expense with all required fields."""
    # Setup mock UnitOfWork
    uow = MagicMock()

    # Setup mock expense after save
    now = datetime.now()
    saved_expense = ExpensePublic(
        id=123,
        amount=Decimal("50.00"),
        description="Spar",
        date=date_type.today(),
        creator_id=1,
        payer_id=2,
        currency="EUR",
        split_type=SplitType.EVEN,
        status=ExpenseStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    uow.expenses.save.return_value = saved_expense

    # Act
    result = create_expense(
        uow=uow,
        amount=Decimal("50.00"),
        description="Spar",
        creator_id=1,
        payer_id=2,
        member_ids=[1, 2],
        currency="EUR",
    )

    # Assert
    assert result.id == 123
    assert result.amount == Decimal("50.00")
    assert result.description == "Spar"
    assert result.currency == "EUR"
    assert result.split_type == SplitType.EVEN
    assert result.status == ExpenseStatus.PENDING
    uow.expenses.save.assert_called_once()


def test_create_expense_with_explicit_currency(mocker):
    """Test creating an expense with explicit currency."""
    uow = MagicMock()

    now = datetime.now()
    saved_expense = ExpensePublic(
        id=124,
        amount=Decimal("100.00"),
        description="USD expense",
        date=date_type.today(),
        creator_id=1,
        payer_id=2,
        currency="USD",
        split_type=SplitType.EVEN,
        status=ExpenseStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    uow.expenses.save.return_value = saved_expense

    result = create_expense(
        uow=uow,
        amount=Decimal("100.00"),
        description="USD expense",
        creator_id=1,
        payer_id=2,
        currency="USD",
        member_ids=[1, 2],
    )

    assert result.currency == "USD"
