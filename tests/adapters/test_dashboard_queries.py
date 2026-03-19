"""Tests for dashboard query module."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlmodel import Session

from app.adapters.sqlalchemy.queries.dashboard_queries import (
    calculate_balance,
    get_group_expenses,
    get_this_month_total,
)
from app.adapters.sqlalchemy.orm_models import GroupRow, MembershipRow, UserRow, ExpenseRow
from app.domain.models import MemberRole, SplitType, ExpenseStatus


class TestGetGroupExpenses:
    """Verify get_group_expenses returns expenses sorted newest first."""

    def test_get_group_expenses_returns_all_expenses_sorted_newest_first(
        self, db_session: Session
    ):
        """Verify all expenses are returned, sorted by date descending."""
        # Create test users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
            role="USER",
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
            role="USER",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # Create group
        group = GroupRow(
            name="Test Group",
            singleton_guard=True,
            default_currency="EUR",
            default_split_type=SplitType.EVEN,
        )
        db_session.add(group)
        db_session.flush()

        # Add members
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user1.id, role=MemberRole.ADMIN)
        )
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user2.id, role=MemberRole.USER)
        )
        db_session.flush()

        # Create expenses on different dates
        today = date.today()
        exp1 = ExpenseRow(
            group_id=group.id,
            amount=Decimal("100.00"),
            description="Spar",
            date=today - timedelta(days=3),
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        exp2 = ExpenseRow(
            group_id=group.id,
            amount=Decimal("50.00"),
            description="Netflix",
            date=today - timedelta(days=1),
            creator_id=user2.id,
            payer_id=user2.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        exp3 = ExpenseRow(
            group_id=group.id,
            amount=Decimal("75.00"),
            description="Groceries",
            date=today,
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        db_session.add(exp1)
        db_session.add(exp2)
        db_session.add(exp3)
        db_session.commit()

        # Fetch
        expenses = get_group_expenses(db_session, group.id)

        # Verify order and count
        assert len(expenses) == 3
        assert expenses[0].id == exp3.id  # Today
        assert expenses[1].id == exp2.id  # 1 day ago
        assert expenses[2].id == exp1.id  # 3 days ago
        assert expenses[0].date > expenses[1].date > expenses[2].date

    def test_get_group_expenses_empty_group(self, db_session: Session):
        """Verify empty list for group with no expenses."""
        group = GroupRow(
            name="Empty Group",
            singleton_guard=True,
            default_currency="EUR",
            default_split_type=SplitType.EVEN,
        )
        db_session.add(group)
        db_session.commit()

        expenses = get_group_expenses(db_session, group.id)
        assert expenses == []


class TestCalculateBalance:
    """Verify balance calculation for even splits."""

    def test_zero_balance_returns_all_square(self, db_session: Session):
        """When expenses balance out, show 'All square!'."""
        # Create users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
            role="USER",
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
            role="USER",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # Create group
        group = GroupRow(
            name="Balanced Group",
            singleton_guard=True,
            default_currency="EUR",
            default_split_type=SplitType.EVEN,
        )
        db_session.add(group)
        db_session.flush()

        # Add members
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user1.id, role=MemberRole.ADMIN)
        )
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user2.id, role=MemberRole.USER)
        )
        db_session.flush()

        # Create equal expenses
        db_session.add(
            ExpenseRow(
                group_id=group.id,
                amount=Decimal("100.00"),
                description="Exp1",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        db_session.add(
            ExpenseRow(
                group_id=group.id,
                amount=Decimal("100.00"),
                description="Exp2",
                date=date.today(),
                creator_id=user2.id,
                payer_id=user2.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        db_session.commit()

        balance = calculate_balance(db_session, group.id, user1.id)

        assert balance["current_user_is_owed"] == Decimal("0.00")
        assert balance["formatted_message"] == "All square!"

    def test_balance_positive_user_is_owed(self, db_session: Session):
        """When payer owes current user, balance is positive."""
        # Create users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
            role="USER",
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
            role="USER",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # Create group
        group = GroupRow(
            name="Owed Group",
            singleton_guard=True,
            default_currency="EUR",
            default_split_type=SplitType.EVEN,
        )
        db_session.add(group)
        db_session.flush()

        # Add members
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user1.id, role=MemberRole.ADMIN)
        )
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user2.id, role=MemberRole.USER)
        )
        db_session.flush()

        # user1 pays 100 (50 is for user2) → user2 owes user1 €50
        db_session.add(
            ExpenseRow(
                group_id=group.id,
                amount=Decimal("100.00"),
                description="Paid by user1",
                date=date.today(),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        db_session.commit()

        balance = calculate_balance(db_session, group.id, user1.id)

        assert balance["current_user_is_owed"] == Decimal("50.00")
        assert "owes you" in balance["formatted_message"]

    def test_balance_negative_user_owes(self, db_session: Session):
        """When other user paid, balance is negative."""
        # Create users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
            role="USER",
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
            role="USER",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # Create group
        group = GroupRow(
            name="Owes Group",
            singleton_guard=True,
            default_currency="EUR",
            default_split_type=SplitType.EVEN,
        )
        db_session.add(group)
        db_session.flush()

        # Add members
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user1.id, role=MemberRole.ADMIN)
        )
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user2.id, role=MemberRole.USER)
        )
        db_session.flush()

        # user2 pays 100 (50 is for user1) → user1 owes user2 €50
        db_session.add(
            ExpenseRow(
                group_id=group.id,
                amount=Decimal("100.00"),
                description="Paid by user2",
                date=date.today(),
                creator_id=user2.id,
                payer_id=user2.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )
        db_session.commit()

        balance = calculate_balance(db_session, group.id, user1.id)

        assert balance["current_user_is_owed"] == Decimal("-50.00")
        assert "You owe partner" in balance["formatted_message"]


class TestGetThisMonthTotal:
    """Verify monthly total calculation."""

    def test_this_month_sums_only_current_month_expenses(self, db_session: Session):
        """Verify only current month expenses are summed."""
        # Create users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
            role="USER",
        )
        db_session.add(user1)
        db_session.flush()

        # Create group
        group = GroupRow(
            name="Month Group",
            singleton_guard=True,
            default_currency="EUR",
            default_split_type=SplitType.EVEN,
        )
        db_session.add(group)
        db_session.flush()

        # Add member
        db_session.add(
            MembershipRow(group_id=group.id, user_id=user1.id, role=MemberRole.ADMIN)
        )
        db_session.flush()

        today = date.today()

        # Create expense this month
        db_session.add(
            ExpenseRow(
                group_id=group.id,
                amount=Decimal("50.00"),
                description="This month",
                date=today,
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )

        # Create expense last month (should not be included)
        db_session.add(
            ExpenseRow(
                group_id=group.id,
                amount=Decimal("100.00"),
                description="Last month",
                date=today - timedelta(days=35),
                creator_id=user1.id,
                payer_id=user1.id,
                currency="EUR",
                split_type=SplitType.EVEN,
                status=ExpenseStatus.PENDING,
            )
        )

        db_session.commit()

        total = get_this_month_total(db_session, group.id)

        assert total == Decimal("50.00")
