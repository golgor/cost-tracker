"""Read-only queries for the external API (Glance Dashboard integration)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlmodel import Session, func, select

from app.adapters.sqlalchemy.orm_models import ExpenseRow, ExpenseSplitRow
from app.adapters.sqlalchemy.queries.dashboard_queries import get_all_users, get_filtered_expenses
from app.domain.balance import calculate_balances_from_splits, minimize_transactions


def get_this_month_expense_count(session: Session) -> int:
    """Count expenses in the current calendar month."""
    today = date.today()
    first_of_month = date(today.year, today.month, 1)

    if today.month == 12:
        last_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)

    statement = (
        select(func.count())
        .select_from(ExpenseRow)
        .where(ExpenseRow.date >= first_of_month)
        .where(ExpenseRow.date <= last_of_month)
    )
    return session.exec(statement).one()


def get_balance_summary(session: Session) -> dict[str, Any]:
    """Compute balance from both partners' perspectives.

    Uses calculate_balances_from_splits() (same as dashboard and settlement
    flows) to ensure consistent results across all views.

    Returns: {
        "net_amount": str (Decimal),
        "direction": str (e.g. "Alice owes Bob" or "All square"),
        "members": [{"name": str, "net": str}, ...]
    }
    """
    users = get_all_users(session)
    names = {u.id: u.display_name for u in users}
    member_ids = list(names.keys())

    if len(member_ids) < 2:
        return {
            "net_amount": "0.00",
            "direction": "All square",
            "members": [{"name": names.get(uid, "Unknown"), "net": "0.00"} for uid in member_ids],
        }

    # Fetch all pending expenses
    expenses = get_filtered_expenses(session, status="PENDING")

    # Load persisted splits
    splits_by_expense: dict[int, list[tuple[int, Decimal]]] = {}
    for expense in expenses:
        rows = session.exec(
            select(ExpenseSplitRow).where(ExpenseSplitRow.expense_id == expense.id)
        ).all()
        splits_by_expense[expense.id] = [(r.user_id, r.amount) for r in rows]

    # Use shared domain logic
    balances = calculate_balances_from_splits(expenses, splits_by_expense, member_ids)
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

    two_dp = Decimal("0.01")
    return {
        "net_amount": str(net.quantize(two_dp)),
        "direction": direction,
        "members": [
            {"name": names[uid], "net": str(balances[uid].net_balance.amount.quantize(two_dp))}
            for uid in member_ids
        ],
    }
