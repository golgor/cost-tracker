"""Read-only queries for dashboard display."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, func, select

from app.adapters.sqlalchemy.orm_models import (
    ExpenseNoteRow,
    ExpenseRow,
    ExpenseSplitRow,
    RecurringDefinitionRow,
    UserRow,
)
from app.adapters.sqlalchemy.queries.mappings import expense_row_to_public
from app.domain.balance import calculate_balances_from_splits
from app.domain.models import ExpensePublic, UserPublic


def get_all_users(session: Session) -> list[UserPublic]:
    """Fetch all users.

    Used for member lists, payer dropdowns, and split calculations.
    """
    rows = session.exec(select(UserRow)).all()
    return [
        UserPublic(
            id=row.id,
            oidc_sub=row.oidc_sub,
            email=row.email,
            display_name=row.display_name,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
        if row.id is not None
    ]


def get_all_expenses(session: Session, limit: int = 100) -> list[ExpensePublic]:
    """Fetch all expenses, newest first.

    Used for dashboard expense feed. Sorted by date descending for feed display.
    """
    statement = (
        select(ExpenseRow)
        .order_by(
            ExpenseRow.date.desc()  # type: ignore[attr-defined] - SQLAlchemy column descriptor
        )
        .limit(limit)
    )
    rows = session.exec(statement).all()

    return [expense_row_to_public(row) for row in rows]


def get_filtered_expenses(
    session: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    payer_id: int | None = None,
    status: str | None = None,
    search_query: str | None = None,
    limit: int | None = None,
) -> list[ExpensePublic]:
    """Fetch expenses with optional filters, sorted newest first.

    Args:
        session: Database session
        date_from: Optional start date (inclusive)
        date_to: Optional end date (inclusive)
        payer_id: Optional payer user ID filter
        status: Optional expense status filter (e.g., 'PENDING', 'SETTLED')
        search_query: Optional keyword search against description and note content (ILIKE)
        limit: Maximum number of results (no limit by default)

    Returns:
        List of expenses matching filters

    Used by /expenses route for filtered expense list viewing.
    """
    statement = select(ExpenseRow)

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
    )
    if limit:
        statement = statement.limit(limit)

    rows = session.exec(statement).all()
    return [expense_row_to_public(row) for row in rows]


def calculate_balance(
    session: Session,
    user_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    payer_id: int | None = None,
    search_query: str | None = None,
) -> dict:
    """Calculate current balance using persisted split amounts.

    Delegates to the same calculate_balances_from_splits() used by the
    settlement flow, ensuring consistent results. Fetches filtered pending
    expenses, loads their splits, then computes net balances.

    Returns: {
        "current_user_is_owed": Decimal,
        "partner_id": int | None,
        "formatted_message": str,
        "is_positive": bool,
        "is_negative": bool,
        "is_zero": bool,
    }
    """
    users = get_all_users(session)
    if not users:
        return {
            "current_user_is_owed": Decimal("0.00"),
            "partner_id": None,
            "formatted_message": "All square!",
        }

    other_users = [u.id for u in users if u.id != user_id]
    partner_id = other_users[0] if other_users else None
    member_ids = [u.id for u in users]

    # Fetch pending expenses with optional filters
    expenses = get_filtered_expenses(
        session,
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

    # Load persisted splits for each expense
    splits_by_expense: dict[int, list[tuple[int, Decimal]]] = {}
    for expense in expenses:
        rows = session.exec(
            select(ExpenseSplitRow).where(ExpenseSplitRow.expense_id == expense.id)
        ).all()
        splits_by_expense[expense.id] = [(r.user_id, r.amount) for r in rows]

    # Use shared domain logic (same as settlement flow)
    balances = calculate_balances_from_splits(expenses, splits_by_expense, member_ids)
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


def get_this_month_total(session: Session) -> Decimal:
    """Sum all expenses in the current calendar month.

    Used for "This Month" widget display.
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
        .where(ExpenseRow.date >= first_of_month)
        .where(ExpenseRow.date <= last_of_month)
    )
    result = session.exec(statement).first()

    return result or Decimal("0.00")
