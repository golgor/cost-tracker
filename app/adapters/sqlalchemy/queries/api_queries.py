"""Read-only queries for the external API (Glance Dashboard integration)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlmodel import Session, func, select

from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    ExpenseSplitRow,
    GroupRow,
    MembershipRow,
    UserRow,
)
from app.domain.models import ExpenseStatus


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
    return session.exec(statement).scalar_one()


def _get_member_display_names(session: Session, group_id: int) -> dict[int, str]:
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

    Returns: {
        "net_amount": str (Decimal),
        "direction": str (e.g. "Alice owes Bob" or "All square"),
        "members": [{"name": str, "net": str}, ...]
    }

    Positive net = member is owed money; negative = member owes money.
    """
    names = _get_member_display_names(session, group_id)
    member_ids = list(names.keys())

    if len(member_ids) < 2:
        return {
            "net_amount": "0.00",
            "direction": "All square",
            "members": [{"name": names.get(uid, "Unknown"), "net": "0.00"} for uid in member_ids],
        }

    # Sum splits for all pending expenses (PENDING excludes both GIFT and SETTLED)
    statement = (
        select(ExpenseSplitRow, ExpenseRow.payer_id)
        .join(ExpenseRow, ExpenseSplitRow.expense_id == ExpenseRow.id)  # ty: ignore[invalid-argument-type]
        .where(
            ExpenseRow.group_id == group_id,
            ExpenseRow.status == ExpenseStatus.PENDING,
        )
    )
    results = session.exec(statement).all()

    # Group splits by expense
    expense_splits: dict[int, list[tuple[int, Decimal, int]]] = {}
    for split_row, payer_id in results:
        eid = split_row.expense_id
        if eid not in expense_splits:
            expense_splits[eid] = []
        expense_splits[eid].append((split_row.user_id, split_row.amount, payer_id))

    # Calculate net balance per member
    # For each expense: payer is owed the sum of others' splits; each non-payer owes their split
    balances: dict[int, Decimal] = {uid: Decimal("0.00") for uid in member_ids}

    for _eid, splits in expense_splits.items():
        expense_payer_id = splits[0][2] if splits else None
        for member_id, amount, _ in splits:
            if member_id == expense_payer_id:
                # Payer's own split — no transfer needed
                continue
            if expense_payer_id is not None and expense_payer_id in balances:
                # Payer is owed this amount
                balances[expense_payer_id] += amount
            if member_id in balances:
                # This member owes this amount
                balances[member_id] -= amount

    # Handle legacy expenses without splits (even 50/50)
    expenses_without_splits = (
        select(ExpenseRow)
        .where(
            ExpenseRow.group_id == group_id,
            ExpenseRow.status == ExpenseStatus.PENDING,
        )
        .where(ExpenseRow.id.notin_(list(expense_splits.keys()) if expense_splits else [0]))  # ty: ignore[unresolved-attribute]
    )
    legacy_expenses = session.exec(expenses_without_splits).all()

    for expense in legacy_expenses:
        half = expense.amount / 2
        if expense.payer_id in balances:
            balances[expense.payer_id] += half
        for uid in member_ids:
            if uid != expense.payer_id:
                balances[uid] -= half

    # Build direction string from first two members (MVP1: 2 partners)
    a_id, b_id = member_ids[0], member_ids[1]
    net = abs(balances[a_id])

    if balances[a_id] < 0:
        direction = f"{names[a_id]} owes {names[b_id]}"
    elif balances[a_id] > 0:
        direction = f"{names[b_id]} owes {names[a_id]}"
    else:
        direction = "All square"

    return {
        "net_amount": str(net),
        "direction": direction,
        "members": [
            {"name": names[uid], "net": str(balances[uid])}
            for uid in member_ids
        ],
    }
