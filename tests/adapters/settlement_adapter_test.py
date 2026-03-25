"""Tests for SqlAlchemySettlementAdapter."""

from decimal import Decimal

import pytest
from sqlmodel import select

from app.adapters.sqlalchemy.orm_models import (
    AuditRow,
    ExpenseRow,
    SettlementExpenseRow,
    SettlementRow,
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


class TestSettlementAdapter:
    """Tests for settlement adapter."""

    def test_save_settlement_creates_record(
        self, uow: UnitOfWork, test_group, user1, user2, test_expense
    ):
        """Test that saving settlement creates database record."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Verify settlement row exists
        row = uow.session.get(SettlementRow, settlement.id)
        assert row is not None
        assert row.group_id == test_group.id
        assert row.settled_by_id == user1.id
        assert row.total_amount == Decimal("50.00")

    def test_save_settlement_links_expenses(
        self, uow: UnitOfWork, test_group, user1, user2, test_expense
    ):
        """Test that settlement is linked to expenses via join table."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Verify join table entry
        links = uow.session.exec(
            select(SettlementExpenseRow).where(SettlementExpenseRow.settlement_id == settlement.id)
        ).all()

        assert len(links) == 1
        assert links[0].expense_id == test_expense.id

    def test_save_settlement_updates_expense_status(
        self, uow: UnitOfWork, test_group, user1, user2, test_expense
    ):
        """Test that saving settlement marks expenses as SETTLED."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Verify expense status
        expense_row = uow.session.get(ExpenseRow, test_expense.id)
        assert expense_row is not None
        assert expense_row.status == ExpenseStatus.SETTLED

    def test_save_settlement_creates_audit_log(
        self, uow: UnitOfWork, test_group, user1, user2, test_expense
    ):
        """Test that settlement creation logs audit entry."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Verify audit log
        audit_entries = uow.session.exec(
            select(AuditRow).where(
                AuditRow.entity_type == "settlement",
                AuditRow.entity_id == settlement.id,
                AuditRow.action == "settlement_confirmed",
            )
        ).all()

        assert len(audit_entries) >= 1
        entry = audit_entries[-1]
        assert entry.actor_id == user1.id
        assert entry.changes is not None
        assert "expense_ids" in entry.changes

    def test_get_by_id_existing(self, uow: UnitOfWork, test_group, user1, user2, test_expense):
        """Test retrieving settlement by ID."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Fetch via adapter
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

        display_names = {user1.id: "Alice", user2.id: "Bob"}

        # Create two expenses and settle them separately
        with uow:
            expense1 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("50.00"),
                description="Expense 1",
                creator_id=user1.id,
                payer_id=user1.id,
            )
            confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[expense1.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
                reference_id="January 2025",
            )

        # Need to commit and create new expense for second settlement
        with uow:
            expense2 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("60.00"),
                description="Expense 2",
                creator_id=user1.id,
                payer_id=user1.id,
            )
            confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[expense2.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
                reference_id="February 2025",
            )

        # List settlements
        settlements = uow.settlements.list_by_group(test_group.id)
        assert len(settlements) == 2
        # Newest first
        assert settlements[0].reference_id == "February 2025"
        assert settlements[1].reference_id == "January 2025"

    def test_get_expense_ids(self, uow: UnitOfWork, test_group, user1, user2):
        """Test retrieving linked expense IDs."""
        from app.domain.use_cases.expenses import create_expense

        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            expense1 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("50.00"),
                description="Expense 1",
                creator_id=user1.id,
                payer_id=user1.id,
            )
            expense2 = create_expense(
                uow=uow,
                group_id=test_group.id,
                amount=Decimal("60.00"),
                description="Expense 2",
                creator_id=user1.id,
                payer_id=user1.id,
            )
            settlement = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[expense1.id, expense2.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Get linked expense IDs
        expense_ids = uow.settlements.get_expense_ids(settlement.id)
        assert len(expense_ids) == 2
        assert expense1.id in expense_ids
        assert expense2.id in expense_ids


class TestSettlementRoundTrip:
    """Contract tests for domain model to ORM and back."""

    def test_settlement_round_trip(self, uow: UnitOfWork, test_group, user1, user2, test_expense):
        """Test domain model -> ORM row -> domain model preserves data."""
        display_names = {user1.id: "Alice", user2.id: "Bob"}

        with uow:
            original = confirm_settlement(
                uow,
                group_id=test_group.id,
                expense_ids=[test_expense.id],
                settled_by_id=user1.id,
                user_display_names=display_names,
            )

        # Fetch via adapter (goes through _to_public)
        fetched = uow.settlements.get_by_id(original.id)
        assert fetched is not None

        # Verify all fields preserved
        assert fetched.id == original.id
        assert fetched.group_id == original.group_id
        assert fetched.reference_id == original.reference_id
        assert fetched.settled_by_id == original.settled_by_id
        assert fetched.total_amount == original.total_amount
        assert fetched.transfer_from_user_id == original.transfer_from_user_id
        assert fetched.transfer_to_user_id == original.transfer_to_user_id
