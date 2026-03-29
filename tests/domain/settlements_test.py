"""Tests for settlement domain use cases."""

from datetime import UTC, date
from decimal import Decimal

import pytest

from app.domain.balance import SettlementTransaction, calculate_balances, minimize_transactions
from app.domain.errors import EmptySettlementError, StaleExpenseError
from app.domain.models import ExpenseStatus
from app.domain.splits import BalanceConfig
from app.domain.use_cases.settlements import (
    confirm_settlement,
    format_transfer_message,
    generate_reference_id,
)


@pytest.fixture
def user1(uow):
    """Create first test user."""
    with uow:
        user = uow.users.save(
            oidc_sub="user1@test.com",
            email="user1@test.com",
            display_name="Alice",
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
        )
    return user


@pytest.fixture
def test_expense(user1, user2, uow):
    """Create a test expense."""
    from app.domain.use_cases.expenses import create_expense

    with uow:
        expense = create_expense(
            uow=uow,
            amount=Decimal("100.00"),
            description="Test expense",
            creator_id=user1.id,
            payer_id=user1.id,
            member_ids=[user1.id, user2.id],
            currency="EUR",
        )
    return expense


class TestFormatTransferMessage:
    """Tests for format_transfer_message function."""

    def test_format_transfer_message_empty(self):
        """Test message for no transactions."""
        message = format_transfer_message([], {})
        assert message == "No payment needed"

    def test_format_transfer_message_single(self):
        """Test message for single transaction."""
        tx = SettlementTransaction(from_user_id=1, to_user_id=2, amount=Decimal("50.00"))
        message = format_transfer_message([tx], {1: "Alice", 2: "Bob"})
        assert message == "Alice pays Bob"

    def test_format_transfer_message_multiple(self):
        """Test message for multiple transactions."""
        tx1 = SettlementTransaction(from_user_id=1, to_user_id=2, amount=Decimal("50.00"))
        tx2 = SettlementTransaction(from_user_id=1, to_user_id=3, amount=Decimal("25.00"))
        message = format_transfer_message([tx1, tx2], {1: "Alice", 2: "Bob", 3: "Carol"})
        assert message == "2 payments required"

    def test_format_transfer_message_unknown_user(self):
        """Test message with unknown user IDs."""
        tx = SettlementTransaction(from_user_id=1, to_user_id=2, amount=Decimal("50.00"))
        message = format_transfer_message([tx], {})
        assert message == "User 1 pays User 2"


class TestGenerateReferenceId:
    """Tests for generate_reference_id function."""

    def test_generate_reference_id_format(self, uow):
        """Test reference ID follows Month Year format."""
        with uow:
            ref = generate_reference_id(uow)

        import calendar

        current_month = calendar.month_name[date.today().month]
        assert current_month in ref
        assert str(date.today().year) in ref

    def test_generate_reference_id_unique(self, uow, user1, user2, test_expense):
        """Test duplicate reference IDs get numbered suffix."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}
        member_ids = list(display_names.keys())

        with uow:
            settlement1 = confirm_settlement(
                uow,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        from app.domain.use_cases.expenses import create_expense

        with uow:
            create_expense(
                uow=uow,
                amount=Decimal("50.00"),
                description="Another expense",
                creator_id=user1.id,
                payer_id=user1.id,
                member_ids=[user1.id, user2.id],
                currency="EUR",
            )

        with uow:
            ref2 = generate_reference_id(uow)
            assert ref2 != settlement1.reference_id


class TestConfirmSettlement:
    """Tests for confirm_settlement function."""

    def test_confirm_settlement_creates_record(self, uow, user1, user2, test_expense):
        """Test settlement creation and expense status update."""
        member_ids = [user1.id, user2.id]

        with uow:
            settlement = confirm_settlement(
                uow,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        assert settlement.id > 0
        assert settlement.settled_by_id == user1.id
        assert settlement.reference_id

        with uow:
            updated_expense = uow.expenses.get_by_id(test_expense.id)
            assert updated_expense.status == ExpenseStatus.SETTLED

    def test_confirm_settlement_empty_expenses_raises_error(self, uow, user1):
        """Test that empty expense list raises error."""
        with pytest.raises(EmptySettlementError), uow:
            confirm_settlement(
                uow,
                expense_ids=[],
                settled_by_id=user1.id,
                member_ids=[user1.id],
            )

    def test_confirm_settlement_already_settled_raises_error(self, uow, user1, user2, test_expense):
        """Test that already settled expenses raise error."""
        from app.adapters.sqlalchemy.orm_models import ExpenseRow

        with uow:
            row = uow.session.get(ExpenseRow, test_expense.id)
            assert row is not None
            row.status = ExpenseStatus.SETTLED
            uow.session.add(row)
            uow.session.commit()

        member_ids = [user1.id, user2.id]

        with pytest.raises(StaleExpenseError), uow:
            confirm_settlement(
                uow,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

    def test_confirm_settlement_stores_transactions(self, uow, user1, user2, test_expense):
        """Test that settlement stores transactions."""
        member_ids = [user1.id, user2.id]

        with uow:
            settlement = confirm_settlement(
                uow,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

            transactions = uow.settlements.get_transactions(settlement.id)

        assert len(transactions) == 1
        assert transactions[0].from_user_id == user2.id
        assert transactions[0].to_user_id == user1.id
        assert transactions[0].amount == Decimal("50.00")

    def test_confirm_settlement_multiple_expenses(self, uow, user1, user2):
        """Test settlement with multiple expenses."""
        from app.domain.use_cases.expenses import create_expense

        with uow:
            expense1 = create_expense(
                uow=uow,
                amount=Decimal("100.00"),
                description="Expense 1",
                creator_id=user1.id,
                payer_id=user1.id,
                member_ids=[user1.id, user2.id],
                currency="EUR",
            )
            expense2 = create_expense(
                uow=uow,
                amount=Decimal("50.00"),
                description="Expense 2",
                creator_id=user1.id,
                payer_id=user2.id,
                member_ids=[user1.id, user2.id],
                currency="EUR",
            )

        member_ids = [user1.id, user2.id]

        with uow:
            settlement = confirm_settlement(
                uow,
                expense_ids=[expense1.id, expense2.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

            transactions = uow.settlements.get_transactions(settlement.id)

        assert len(transactions) == 1
        assert transactions[0].from_user_id == user2.id
        assert transactions[0].to_user_id == user1.id
        assert transactions[0].amount == Decimal("25.00")

        with uow:
            for exp_id in [expense1.id, expense2.id]:
                expense = uow.expenses.get_by_id(exp_id)
                assert expense.status == ExpenseStatus.SETTLED


class TestCalculateBalancesIntegration:
    """Tests for balance calculation integration."""

    def test_calculate_balances_two_person_even_split(self, user1, user2):
        """Test balance calculation for 2-person even split."""
        from datetime import datetime

        from app.domain.models import ExpensePublic

        now = datetime.now(UTC)
        expenses = [
            ExpensePublic(
                id=1,
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

        config = BalanceConfig()
        balances = calculate_balances(expenses, [user1.id, user2.id], config)

        assert balances[user1.id].net_balance.amount == Decimal("50.00")
        assert balances[user2.id].net_balance.amount == Decimal("-50.00")

    def test_minimize_transactions_two_person(self, user1, user2):
        """Test transaction minimization for 2-person case."""
        from datetime import datetime

        from app.domain.models import ExpensePublic

        now = datetime.now(UTC)
        expenses = [
            ExpensePublic(
                id=1,
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

        config = BalanceConfig()
        balances = calculate_balances(expenses, [user1.id, user2.id], config)
        transactions = minimize_transactions(balances)

        assert len(transactions) == 1
        assert transactions[0].from_user_id == user2.id
        assert transactions[0].to_user_id == user1.id
        assert transactions[0].amount.amount == Decimal("50.00")
