"""Tests for settlement domain use cases."""

from datetime import UTC, date
from decimal import Decimal

import pytest

from app.domain.errors import EmptySettlementError, StaleExpenseError
from app.domain.models import ExpenseStatus
from app.domain.use_cases.settlements import calculate_settlement, confirm_settlement


@pytest.fixture
def user1(uow):
    """Create first test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user1@test.com",
            email="user1@test.com",
            display_name="Alice",
            actor_id=1,
        )
    return user


@pytest.fixture
def user2(uow):
    """Create second test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user2@test.com",
            email="user2@test.com",
            display_name="Bob",
            actor_id=2,
        )
    return user


@pytest.fixture
def test_group(user1, user2, uow):
    """Create a test group with two members."""
    with uow:
        group = uow.groups.save(name="Test Household", actor_id=user1.id)
        uow.groups.add_member(group.id, user2.id, "USER", actor_id=user1.id)
    return group


@pytest.fixture
def test_expense(user1, test_group, uow):
    """Create a test expense."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            group_id=test_group.id,
            amount=Decimal("100.00"),
            description="Test expense",
            creator_id=user1.id,
            payer_id=user1.id,
        )
    return expense


class TestCalculateSettlement:
    """Tests for calculate_settlement function."""

    def test_calculate_settlement_even_split(self, user1, user2):
        """Test balance calculation for even 50/50 split."""
        from datetime import datetime

        from app.domain.models import ExpensePublic

        now = datetime.now(UTC)
        expenses = [
            ExpensePublic(
                id=1,
                group_id=1,
                amount=Decimal("100.00"),
                description="User1 paid",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type="EVEN",
                status=ExpenseStatus.PENDING,
                created_at=now,
                updated_at=now,
            ),
        ]

        display_names = {user1.id: "Alice", user2.id: "Bob"}
        result = calculate_settlement(expenses, display_names)

        # User1 paid $100, so User2 owes User1 $50
        assert result.transfer_from_user_id == user2.id
        assert result.transfer_to_user_id == user1.id
        assert result.total_amount == Decimal("50.00")
        assert "Bob pays Alice" in result.transfer_message

    def test_calculate_settlement_balanced_expenses(self, user1, user2):
        """Test when both users have paid equal amounts."""
        from datetime import datetime

        from app.domain.models import ExpensePublic

        now = datetime.now(UTC)
        expenses = [
            ExpensePublic(
                id=1,
                group_id=1,
                amount=Decimal("100.00"),
                description="User1 paid",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type="EVEN",
                status=ExpenseStatus.PENDING,
                created_at=now,
                updated_at=now,
            ),
            ExpensePublic(
                id=2,
                group_id=1,
                amount=Decimal("100.00"),
                description="User2 paid",
                date=date.today(),
                creator_id=user2.id,
                payer_id=user2.id,
                currency="EUR",
                split_type="EVEN",
                status=ExpenseStatus.PENDING,
                created_at=now,
                updated_at=now,
            ),
        ]

        display_names = {user1.id: "Alice", user2.id: "Bob"}
        result = calculate_settlement(expenses, display_names)

        # Both paid equal amounts, so no transfer needed
        assert result.total_amount == Decimal("0.00")
        assert (
            "balanced" in result.transfer_message.lower() or "No payment" in result.transfer_message
        )

    def test_calculate_settlement_no_expenses(self):
        """Test with empty expense list."""
        result = calculate_settlement([], {})

        assert result.total_amount == Decimal("0.00")
        assert "select" in result.transfer_message.lower()


class TestConfirmSettlement:
    """Tests for confirm_settlement function."""

    def test_confirm_settlement_creates_record(self, uow, test_group, user1, user2, test_expense):
        """Test settlement creation and expense status update."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Verify settlement was created
        assert settlement.id > 0
        assert settlement.group_id == test_group.id
        assert settlement.settled_by_id == user1.id
        assert settlement.total_amount == Decimal("50.00")  # Half of $100

        # Verify expense status was updated
        with uow:
            updated_expense = uow.expenses.get_by_id(test_expense.id)
            assert updated_expense.status == ExpenseStatus.SETTLED

    def test_confirm_settlement_empty_expenses_raises_error(self, uow, test_group, user1):
        """Test that empty expense list raises error."""
        display_names = {user1.id: "Alice"}

        with pytest.raises(EmptySettlementError), uow:
            confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

    def test_confirm_settlement_already_settled_raises_error(
        self, uow, test_group, user1, user2, test_expense
    ):
        """Test that already settled expenses raise error."""
        from app.adapters.sqlalchemy.orm_models import ExpenseRow

        # Mark expense as settled
        with uow:
            row = uow.session.get(ExpenseRow, test_expense.id)
            assert row is not None
            row.status = ExpenseStatus.SETTLED
            uow.session.add(row)
            uow.session.commit()

        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with pytest.raises(StaleExpenseError), uow:
            confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

    def test_confirm_settlement_creates_reference_id(
        self, uow, test_group, user1, user2, test_expense
    ):
        """Test that settlement gets a reference ID."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Reference ID should follow "Month Year" format
        assert settlement.reference_id
        # Should contain the current month name
        import calendar

        current_month = calendar.month_name[date.today().month]
        assert current_month in settlement.reference_id

    def test_confirm_settlement_multiple_expenses(self, uow, test_group, user1, user2):
        """Test settlement with multiple expenses."""
        from app.domain.use_cases.expenses import create_expense

        with uow:
            expense1 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("100.00"),
                description="Expense 1",
                creator_id=user1.id,
                payer_id=user1.id,
            )
            expense2 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("50.00"),
                description="Expense 2",
                creator_id=user1.id,
                payer_id=user2.id,  # User2 paid this one
            )

        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[expense1.id, expense2.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # User1 paid $100 (owed $50), User2 paid $50 (owed $25)
        # Net: User1 is owed $25 by User2
        assert settlement.total_amount == Decimal("25.00")

        # Verify both expenses are settled
        with uow:
            for exp_id in [expense1.id, expense2.id]:
                expense = uow.expenses.get_by_id(exp_id)
                assert expense.status == ExpenseStatus.SETTLED
