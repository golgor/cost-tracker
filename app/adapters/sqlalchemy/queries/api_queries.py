"""Read-only queries for the external API (Glance Dashboard integration)."""

from datetime import date, timedelta
from typing import Any

from sqlmodel import Session, func, select

from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    GroupRow,
    MembershipRow,
    UserRow,
)
from app.adapters.sqlalchemy.queries.dashboard_queries import get_filtered_expenses
from app.domain.balance import calculate_balances, minimize_transactions
from app.domain.splits.config import BalanceConfig


def get_default_group_id(session: Session) -> int | None:
    """Get the ID of the default (singleton) group, or None if no group exists."""
    row = session.exec(select(GroupRow).limit(1)).first()
    return row.id if row else None


def get_group_currency(session: Session, group_id: int) -> str:
    """Get the default currency for a group."""
    row = session.get(GroupRow, group_id)
    return row.default_currency if row else "EUR"


def get_this_month_expense_count(session: Session, group_id: int) -> int:
    """Count expenses in the current calendar month for a group."""
    today = date.today()
    first_of_month = date(today.year, today.month, 1)

    if today.month == 12:
        last_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)

    statement = (
        select(func.count())
        .select_from(ExpenseRow)
        .where(ExpenseRow.group_id == group_id)
        .where(ExpenseRow.date >= first_of_month)
        .where(ExpenseRow.date <= last_of_month)
    )
    return session.exec(statement).one()


def get_member_display_names(session: Session, group_id: int) -> dict[int, str]:
    """Fetch {user_id: display_name} for all members of a group."""
    statement = (
        select(UserRow.id, UserRow.display_name)
        .join(MembershipRow, MembershipRow.user_id == UserRow.id)  # type: ignore[arg-type]
        .where(MembershipRow.group_id == group_id)
    )
    rows = session.exec(statement).all()
    return {row[0]: row[1] for row in rows}  # type: ignore[index]


def get_balance_summary(session: Session, group_id: int) -> dict[str, Any]:
    """Compute balance from both members' perspectives.

    Uses the same domain logic as the settlement flow (calculate_balances +
    minimize_transactions) to ensure consistent results.

    Returns: {
        "net_amount": str (Decimal),
        "direction": str (e.g. "Alice owes Bob" or "All square"),
        "members": [{"name": str, "net": str}, ...]
    }

    Positive net = member is owed money; negative = member owes money.
    """
    names = get_member_display_names(session, group_id)
    member_ids = list(names.keys())

    if len(member_ids) < 2:
        return {
            "net_amount": "0.00",
            "direction": "All square",
            "members": [{"name": names.get(uid, "Unknown"), "net": "0.00"} for uid in member_ids],
        }

    # Fetch all pending expenses and compute balance using proven domain logic
    expenses = get_filtered_expenses(session, group_id, status="PENDING")
    config = BalanceConfig()
    balances = calculate_balances(expenses, member_ids, config)
    transactions = minimize_transactions(balances)

    # Build direction string from transactions
    if transactions:
        tx = transactions[0]
        from_name = names.get(tx.from_user_id, "Unknown")
        to_name = names.get(tx.to_user_id, "Unknown")
        direction = f"{from_name} owes {to_name}"
        net = tx.amount.amount
    else:
        direction = "All square"
        net = abs(balances[member_ids[0]].net_balance.amount)

    return {
        "net_amount": str(net),
        "direction": direction,
        "members": [
            {"name": names[uid], "net": str(balances[uid].net_balance.amount)} for uid in member_ids
        ],
    }
