"""Tests for SqlAlchemySettlementAdapter."""

from decimal import Decimal

import pytest
from sqlmodel import select

from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    SettlementExpenseRow,
    SettlementRow,
    SettlementTransactionRow,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.domain.models import ExpenseStatus
from app.domain.use_cases.settlements import confirm_settlement


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
def test_group(user1, user2, uow):
    """Create a test group with two members."""
    with uow:
        group = uow.groups.save(name="Test Household")
        uow.groups.add_member(group.id, user1.id, "ADMIN")
        uow.groups.add_member(group.id, user2.id, "USER")
    return group


@pytest.fixture
def test_expense(user1, user2, test_group, uow):
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
            member_ids=[user1.id, user2.id],
        )
    return expense


class TestSettlementAdapter:
    """Tests for settlement adapter."""

    def test_save_settlement_creates_record(
        self, uow: UnitOfWork, test_group, user1, user2, test_expense
    ):
        """Test that saving settlement creates database record."""
        member_ids = [user1.id, user2.id]

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        row = uow.session.get(SettlementRow, settlement.id)
        assert row is not None
        assert row.group_id == test_group.id
        assert row.settled_by_id == user1.id

    def test_save_settlement_creates_transactions(
        self, uow: UnitOfWork, test_group, user1, user2, test_expense
    ):
        """Test that saving settlement creates transaction records."""
        member_ids = [user1.id, user2.id]

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        transactions = uow.session.exec(
            select(SettlementTransactionRow).where(
                SettlementTransactionRow.settlement_id == settlement.id
            )
        ).all()

        assert len(transactions) == 1
        assert transactions[0].from_user_id == user2.id
        assert transactions[0].to_user_id == user1.id
        assert transactions[0].amount == Decimal("50.00")

    def test_save_settlement_links_expenses(
        self, uow: UnitOfWork, test_group, user1, user2, test_expense
    ):
        """Test that settlement is linked to expenses via join table."""
        member_ids = [user1.id, user2.id]

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        links = uow.session.exec(
            select(SettlementExpenseRow).where(SettlementExpenseRow.settlement_id == settlement.id)
        ).all()

        assert len(links) == 1
        assert links[0].expense_id == test_expense.id

    def test_save_settlement_updates_expense_status(
        self, uow: UnitOfWork, test_group, user1, user2, test_expense
    ):
        """Test that saving settlement marks expenses as SETTLED."""
        member_ids = [user1.id, user2.id]

        with uow:
            confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        expense_row = uow.session.get(ExpenseRow, test_expense.id)
        assert expense_row is not None
        assert expense_row.status == ExpenseStatus.SETTLED

    def test_get_by_id_existing(self, uow: UnitOfWork, test_group, user1, user2, test_expense):
        """Test retrieving settlement by ID."""
        member_ids = [user1.id, user2.id]

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        fetched = uow.settlements.get_by_id(settlement.id)
        assert fetched is not None
        assert fetched.id == settlement.id
        assert fetched.reference_id == settlement.reference_id

    def test_get_by_id_not_found(self, uow: UnitOfWork):
        """Test retrieving non-existent settlement returns None."""
        result = uow.settlements.get_by_id(99999)
        assert result is None

    def test_list_by_group_ordered(self, uow: UnitOfWork, test_group, user1, user2):
        """Test settlements are listed newest first."""
        from app.domain.use_cases.expenses import create_expense

        member_ids = [user1.id, user2.id]

        with uow:
            expense1 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("50.00"),
                description="Expense 1",
                creator_id=user1.id,
                payer_id=user1.id,
                member_ids=[user1.id, user2.id],
            )
            confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[expense1.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
                reference_id="January 2025",
            )

        with uow:
            expense2 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("60.00"),
                description="Expense 2",
                creator_id=user1.id,
                payer_id=user1.id,
                member_ids=[user1.id, user2.id],
            )
            confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[expense2.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
                reference_id="February 2025",
            )

        settlements = uow.settlements.list_by_group(test_group.id)
        assert len(settlements) == 2
        assert settlements[0].reference_id == "February 2025"
        assert settlements[1].reference_id == "January 2025"

    def test_get_expense_ids(self, uow: UnitOfWork, test_group, user1, user2):
        """Test retrieving linked expense IDs."""
        from app.domain.use_cases.expenses import create_expense

        member_ids = [user1.id, user2.id]

        with uow:
            expense1 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("50.00"),
                description="Expense 1",
                creator_id=user1.id,
                payer_id=user1.id,
                member_ids=[user1.id, user2.id],
            )
            expense2 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("60.00"),
                description="Expense 2",
                creator_id=user1.id,
                payer_id=user1.id,
                member_ids=[user1.id, user2.id],
            )
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[expense1.id, expense2.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        expense_ids = uow.settlements.get_expense_ids(settlement.id)
        assert len(expense_ids) == 2
        assert expense1.id in expense_ids
        assert expense2.id in expense_ids

    def test_get_transactions(self, uow: UnitOfWork, test_group, user1, user2, test_expense):
        """Test retrieving settlement transactions."""
        member_ids = [user1.id, user2.id]

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        transactions = uow.settlements.get_transactions(settlement.id)
        assert len(transactions) == 1
        assert transactions[0].from_user_id == user2.id
        assert transactions[0].to_user_id == user1.id
        assert transactions[0].amount == Decimal("50.00")


class TestSettlementRoundTrip:
    """Contract tests for domain model to ORM and back."""

    def test_settlement_round_trip(self, uow: UnitOfWork, test_group, user1, user2, test_expense):
        """Test domain model -> ORM row -> domain model preserves data."""
        member_ids = [user1.id, user2.id]

        with uow:
            original = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                member_ids=member_ids,
            )

        fetched = uow.settlements.get_by_id(original.id)
        assert fetched is not None

        assert fetched.id == original.id
        assert fetched.group_id == original.group_id
        assert fetched.reference_id == original.reference_id
        assert fetched.settled_by_id == original.settled_by_id
