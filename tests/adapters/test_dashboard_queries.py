"""Tests for dashboard query module."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session

from app.adapters.sqlalchemy.orm_models import ExpenseRow, UserRow
from app.adapters.sqlalchemy.queries.dashboard_queries import (
    calculate_balance,
    get_all_expenses,
    get_this_month_total,
)
from app.domain.models import ExpenseStatus, SplitType


class TestGetAllExpenses:
    """Verify get_all_expenses returns expenses sorted newest first."""

    def test_get_all_expenses_returns_all_expenses_sorted_newest_first(self, db_session: Session):
        """Verify all expenses are returned, sorted by date descending."""
        # Create test users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # Create expenses on different dates
        today = date.today()
        exp1 = ExpenseRow(
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
        expenses = get_all_expenses(db_session)

        # Verify order and count
        assert len(expenses) == 3
        assert expenses[0].id == exp3.id  # Today
        assert expenses[1].id == exp2.id  # 1 day ago
        assert expenses[2].id == exp1.id  # 3 days ago
        assert expenses[0].date > expenses[1].date > expenses[2].date

    def test_get_all_expenses_empty(self, db_session: Session):
        """Verify empty list when no expenses exist."""
        expenses = get_all_expenses(db_session)
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
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # Create equal expenses
        db_session.add(
            ExpenseRow(
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

        balance = calculate_balance(db_session, user1.id)

        assert balance["current_user_is_owed"] == Decimal("0.00")
        assert balance["formatted_message"] == "All square!"
        assert balance["is_zero"] is True
        assert balance["is_positive"] is False
        assert balance["is_negative"] is False

    def test_balance_positive_user_is_owed(self, db_session: Session):
        """When payer owes current user, balance is positive."""
        # Create users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # user1 pays 100 (50 is for user2) → user2 owes user1 €50
        db_session.add(
            ExpenseRow(
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

        balance = calculate_balance(db_session, user1.id)

        assert balance["current_user_is_owed"] == Decimal("50.00")
        assert "owes you" in balance["formatted_message"]
        assert balance["is_positive"] is True
        assert balance["is_zero"] is False
        assert balance["is_negative"] is False

    def test_balance_negative_user_owes(self, db_session: Session):
        """When other user paid, balance is negative."""
        # Create users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # user2 pays 100 (50 is for user1) → user1 owes user2 €50
        db_session.add(
            ExpenseRow(
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

        balance = calculate_balance(db_session, user1.id)

        assert balance["current_user_is_owed"] == Decimal("-50.00")
        assert "You owe partner" in balance["formatted_message"]
        assert balance["is_negative"] is True
        assert balance["is_zero"] is False
        assert balance["is_positive"] is False

    def test_settled_expenses_excluded_from_balance(self, db_session: Session):
        """Settled expenses should not affect balance calculation."""
        # Create users
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
        )
        user2 = UserRow(
            oidc_sub="user2",
            email="user2@example.com",
            display_name="User Two",
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.flush()

        # Create pending expense (user1 paid 20€)
        expense = ExpenseRow(
            amount=Decimal("20.00"),
            description="Test expense",
            date=date.today(),
            creator_id=user1.id,
            payer_id=user1.id,
            currency="EUR",
            split_type=SplitType.EVEN,
            status=ExpenseStatus.PENDING,
        )
        db_session.add(expense)
        db_session.commit()

        # Balance should show partner owes user1 10€
        balance = calculate_balance(db_session, user1.id)
        assert balance["current_user_is_owed"] == Decimal("10.00")
        assert "owes you" in balance["formatted_message"]

        # Settle the expense
        expense.status = ExpenseStatus.SETTLED
        db_session.commit()

        # Balance should now be zero (settled expenses excluded)
        balance = calculate_balance(db_session, user1.id)
        assert balance["current_user_is_owed"] == Decimal("0.00")
        assert balance["formatted_message"] == "All square!"
        assert balance["is_zero"] is True


class TestGetThisMonthTotal:
    """Verify monthly total calculation."""

    def test_this_month_sums_only_current_month_expenses(self, db_session: Session):
        """Verify only current month expenses are summed."""
        # Create user
        user1 = UserRow(
            oidc_sub="user1",
            email="user1@example.com",
            display_name="User One",
        )
        db_session.add(user1)
        db_session.flush()

        today = date.today()

        # Create expense this month
        db_session.add(
            ExpenseRow(
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

        total = get_this_month_total(db_session)

        assert total == Decimal("50.00")

    def test_this_month_returns_zero_when_no_expenses(self, db_session: Session):
        """Verify zero total when no expenses exist."""
        total = get_this_month_total(db_session)

        assert total == Decimal("0.00")
