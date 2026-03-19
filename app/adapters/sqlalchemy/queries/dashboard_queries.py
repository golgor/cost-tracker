"""Read-only queries for dashboard display."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, func, select

from app.adapters.sqlalchemy.orm_models import ExpenseRow, MembershipRow
from app.domain.models import ExpensePublic, MembershipPublic


def get_group_members(session: Session, group_id: int) -> list[MembershipPublic]:
    """Fetch all members of a group with their roles.

    Used for dashboard to display group member info (badges, names, etc).
    """
    statement = select(MembershipRow).where(MembershipRow.group_id == group_id)
    rows = session.exec(statement).all()

    return [
        MembershipPublic(
            user_id=row.user_id,
            group_id=row.group_id,
            role=row.role,
            joined_at=row.joined_at,
        )
        for row in rows
    ]


def get_group_expenses(session: Session, group_id: int) -> list[ExpensePublic]:
    """Fetch all unsettled expenses for a group, newest first.

    Used for dashboard expense feed. Sorted by date descending for feed display.

    Note: In Epic 4 (Story 4.3), this will filter out gift-status expenses.
    Epic 4 (Story 4.2) will switch to selecting from expense_splits table for split-mode support.
    """
    statement = (
        select(ExpenseRow)
        .where(ExpenseRow.group_id == group_id)
        .order_by(
            ExpenseRow.date.desc()  # type: ignore[attr-defined]
        )
    )
    rows = session.exec(statement).all()

    return [_expense_row_to_public(row) for row in rows]


def calculate_balance(session: Session, group_id: int, user_id: int) -> dict:
    """Calculate current balance for a group using even splits.

    Returns: {
        "current_user_is_owed": Decimal,  # positive = current user is owed, negative = owes
        "partner_id": int,
        "formatted_message": str,  # "All square!" if zero, else formatted balance
    }

    This query assumes even (50/50) split for all expenses.

    In Epic 4 (Story 4.2), this will be refactored to:
    - Sum from expense_splits table for split-mode support
    - Exclude GIFT status expenses (Story 4.3)
    - Handle multiple members (currently assumes 2 partners)
    """
    # Fetch all unsettled expenses for this group
    statement = select(ExpenseRow).where(ExpenseRow.group_id == group_id)
    expenses = session.exec(statement).all()

    # Get group members to identify partner
    members = get_group_members(session, group_id)
    if not members:
        return {
            "current_user_is_owed": Decimal("0.00"),
            "partner_id": None,
            "formatted_message": "All square!",
        }

    # Assumes 2 members; will be generalized in future epics
    other_members = [m.user_id for m in members if m.user_id != user_id]
    partner_id = other_members[0] if other_members else None

    # Calculate balance: sum (amount / 2) if current_user paid, subtract if other user paid
    balance = Decimal("0.00")
    for expense in expenses:
        half = expense.amount / 2
        if expense.payer_id == user_id:
            # Current user paid → partner owes current user
            balance += half
        else:
            # Partner paid → current user owes partner
            balance -= half

    # Format message
    if balance == 0:
        message = "All square!"
    elif balance > 0:
        message = f"Partner owes you €{abs(balance):.2f}"
    else:
        message = f"You owe partner €{abs(balance):.2f}"

    return {
        "current_user_is_owed": balance,
        "partner_id": partner_id,
        "formatted_message": message,
        "is_positive": balance > 0,  # Pre-computed flag for template
        "is_negative": balance < 0,  # Pre-computed flag for template
        "is_zero": balance == 0,  # Pre-computed flag for template
    }


def get_this_month_total(session: Session, group_id: int) -> Decimal:
    """Sum all expenses in the current calendar month for a group.

    Used for "This Month" widget display.

    In Epic 4 (Story 4.3), this will exclude GIFT status expenses.
    """
    today = date.today()
    first_of_month = date(today.year, today.month, 1)

    # Last day of month: first day of next month - 1 day
    if today.month == 12:
        last_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)

    statement = (
        select(func.sum(ExpenseRow.amount))
        .where(ExpenseRow.group_id == group_id)
        .where(ExpenseRow.date >= first_of_month)
        .where(ExpenseRow.date <= last_of_month)
    )
    result = session.exec(statement).first()

    return result or Decimal("0.00")


def _expense_row_to_public(row: ExpenseRow) -> ExpensePublic:
    """Convert ORM row to domain model. Mirrors ExpenseAdapter._to_public()."""
    # row.id is guaranteed to be set for rows fetched from database
    assert row.id is not None, "ExpenseRow.id must be set for persisted rows"
    assert row.created_at is not None
    assert row.updated_at is not None

    return ExpensePublic(
        id=row.id,
        group_id=row.group_id,
        amount=row.amount,
        description=row.description,
        date=row.date,
        creator_id=row.creator_id,
        payer_id=row.payer_id,
        currency=row.currency,
        split_type=row.split_type,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
