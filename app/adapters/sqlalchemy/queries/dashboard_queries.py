"""Read-only queries for dashboard display."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, func, select

from app.adapters.sqlalchemy.orm_models import (
    ExpenseNoteRow,
    ExpenseRow,
    MembershipRow,
    RecurringDefinitionRow,
)
from app.adapters.sqlalchemy.queries.mappings import expense_row_to_public
from app.domain.balance import calculate_balances
from app.domain.models import ExpensePublic, MembershipPublic
from app.domain.splits.config import BalanceConfig


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


def get_group_expenses(session: Session, group_id: int, limit: int = 100) -> list[ExpensePublic]:
    """Fetch all unsettled expenses for a group, newest first.

    Used for dashboard expense feed. Sorted by date descending for feed display.

    Note: In Epic 4 (Story 4.3), this will filter out gift-status expenses.
    Epic 4 (Story 4.2) will switch to selecting from expense_splits table for split-mode support.
    """
    statement = (
        select(ExpenseRow)
        .where(ExpenseRow.group_id == group_id)
        .order_by(
            ExpenseRow.date.desc()  # type: ignore[attr-defined] - SQLAlchemy column descriptor
        )
        .limit(limit)
    )
    rows = session.exec(statement).all()

    return [expense_row_to_public(row) for row in rows]


def get_filtered_expenses(
    session: Session,
    group_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    payer_id: int | None = None,
    status: str | None = None,
    search_query: str | None = None,
    limit: int = 100,
) -> list[ExpensePublic]:
    """Fetch expenses with optional filters, sorted newest first.

    Args:
        session: Database session
        group_id: Group ID to fetch expenses for
        date_from: Optional start date (inclusive)
        date_to: Optional end date (inclusive)
        payer_id: Optional payer user ID filter
        status: Optional expense status filter (e.g., 'PENDING', 'SETTLED')
        search_query: Optional keyword search against description and note content (ILIKE)
        limit: Maximum number of results (default 100)

    Returns:
        List of expenses matching filters

    Used by /expenses route for filtered expense list viewing.
    """
    statement = select(ExpenseRow).where(ExpenseRow.group_id == group_id)

    # Apply optional filters
    if date_from:
        statement = statement.where(ExpenseRow.date >= date_from)
    if date_to:
        statement = statement.where(ExpenseRow.date <= date_to)
    if payer_id:
        statement = statement.where(ExpenseRow.payer_id == payer_id)
    if status:
        statement = statement.where(ExpenseRow.status == status)

    if search_query:
        pattern = f"%{search_query}%"
        statement = (
            statement.outerjoin(  # type: ignore[call-overload]
                ExpenseNoteRow,
                ExpenseNoteRow.expense_id == ExpenseRow.id,  # type: ignore[union-attr]  # ty: ignore[invalid-argument-type]
            )
            .where(
                ExpenseRow.description.ilike(pattern)  # type: ignore[union-attr]
                | ExpenseNoteRow.content.ilike(pattern)  # type: ignore[union-attr]
            )
            .distinct()
        )

    statement = statement.order_by(
        ExpenseRow.date.desc()  # type: ignore[attr-defined] - SQLAlchemy column descriptor
    ).limit(limit)

    rows = session.exec(statement).all()
    return [expense_row_to_public(row) for row in rows]


def calculate_balance(
    session: Session,
    group_id: int,
    user_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    payer_id: int | None = None,
    search_query: str | None = None,
) -> dict:
    """Calculate current balance for a group using domain balance logic.

    Uses the same calculate_balances() function as the settlement flow to
    ensure consistent results. Fetches filtered pending expenses, then
    delegates to the pure domain function.

    Returns: {
        "current_user_is_owed": Decimal,  # positive = current user is owed, negative = owes
        "partner_id": int | None,
        "formatted_message": str,  # "All square!" if zero, else formatted balance
        "is_positive": bool,
        "is_negative": bool,
        "is_zero": bool,
    }

    Optionally filters by date range, payer, and search query.
    """
    # Get group members to identify partner
    members = get_group_members(session, group_id)
    if not members:
        return {
            "current_user_is_owed": Decimal("0.00"),
            "partner_id": None,
            "formatted_message": "All square!",
        }

    other_members = [m.user_id for m in members if m.user_id != user_id]
    partner_id = other_members[0] if other_members else None
    member_ids = [m.user_id for m in members]

    # Fetch pending expenses with optional filters
    expenses = get_filtered_expenses(
        session,
        group_id,
        date_from=date_from,
        date_to=date_to,
        payer_id=payer_id,
        status="PENDING",
        search_query=search_query,
    )

    if not expenses:
        return {
            "current_user_is_owed": Decimal("0.00"),
            "partner_id": partner_id,
            "formatted_message": "All square!",
            "is_positive": False,
            "is_negative": False,
            "is_zero": True,
        }

    # Use proven domain logic (same as settlement flow)
    config = BalanceConfig()
    balances = calculate_balances(expenses, member_ids, config)
    balance = balances[user_id].net_balance.amount

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
        "is_positive": balance > 0,
        "is_negative": balance < 0,
        "is_zero": balance == 0,
    }


def get_recurring_definition_names(session: Session, definition_ids: list[int]) -> dict[int, str]:
    """Return {definition_id: name} for the given IDs.

    Used to show recurring source names on expense cards without fetching full definitions.
    """
    if not definition_ids:
        return {}
    statement = select(RecurringDefinitionRow).where(
        RecurringDefinitionRow.id.in_(definition_ids)  # type: ignore[union-attr]
    )
    rows = session.exec(statement).all()
    return {row.id: row.name for row in rows if row.id is not None}


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
