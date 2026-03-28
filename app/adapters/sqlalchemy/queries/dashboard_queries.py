"""Read-only queries for dashboard display."""

from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, func, select

from app.adapters.sqlalchemy.orm_models import (
    ExpenseNoteRow,
    ExpenseRow,
    ExpenseSplitRow,
    MembershipRow,
    RecurringDefinitionRow,
)
from app.adapters.sqlalchemy.queries.mappings import expense_row_to_public
from app.domain.models import ExpensePublic, ExpenseStatus, MembershipPublic


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


def _filtered_expense_ids_subquery(
    group_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    payer_id: int | None = None,
    search_query: str | None = None,
):
    """Build a subquery of ExpenseRow IDs matching optional filters.

    Used by calculate_balance() to avoid row duplication from note joins
    affecting split-sum calculations.
    """
    stmt = select(ExpenseRow.id).where(  # type: ignore[arg-type]
        ExpenseRow.group_id == group_id,
        ExpenseRow.status == ExpenseStatus.PENDING,
        ExpenseRow.status != ExpenseStatus.GIFT,
    )
    if date_from:
        stmt = stmt.where(ExpenseRow.date >= date_from)
    if date_to:
        stmt = stmt.where(ExpenseRow.date <= date_to)
    if payer_id:
        stmt = stmt.where(ExpenseRow.payer_id == payer_id)
    if search_query:
        pattern = f"%{search_query}%"
        stmt = (
            stmt.outerjoin(  # type: ignore[call-overload]
                ExpenseNoteRow,
                ExpenseNoteRow.expense_id == ExpenseRow.id,  # type: ignore[union-attr]  # ty: ignore[invalid-argument-type]
            )
            .where(
                ExpenseRow.description.ilike(pattern)  # type: ignore[union-attr]
                | ExpenseNoteRow.content.ilike(pattern)  # type: ignore[union-attr]
            )
            .distinct()
        )
    return stmt


def calculate_balance(
    session: Session,
    group_id: int,
    user_id: int,
    date_from: date | None = None,
    date_to: date | None = None,
    payer_id: int | None = None,
    search_query: str | None = None,
) -> dict:
    """Calculate current balance for a group using actual split amounts from expense_splits.

    Returns: {
        "current_user_is_owed": Decimal,  # positive = current user is owed, negative = owes
        "partner_id": int,
        "formatted_message": str,  # "All square!" if zero, else formatted balance
    }

    This query sums from expense_splits table to support all split modes (even, shares,
    percentage, exact). Excludes GIFT status expenses from balance calculation.
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

    # Assumes 2 members; will be generalized in future epics
    other_members = [m.user_id for m in members if m.user_id != user_id]
    partner_id = other_members[0] if other_members else None

    # Query all splits for pending expenses in this group
    # Join with expenses to filter by status and get payer info
    has_filters = any([date_from, date_to, payer_id, search_query])
    statement = (
        select(ExpenseSplitRow, ExpenseRow.payer_id)
        .join(ExpenseRow, ExpenseSplitRow.expense_id == ExpenseRow.id)  # ty: ignore[invalid-argument-type]
        .where(
            ExpenseRow.group_id == group_id,
            ExpenseRow.status == ExpenseStatus.PENDING,
            ExpenseRow.status != ExpenseStatus.GIFT,
        )
    )
    if has_filters:
        filtered_ids = _filtered_expense_ids_subquery(
            group_id, date_from, date_to, payer_id, search_query
        )
        statement = statement.where(ExpenseSplitRow.expense_id.in_(filtered_ids))  # type: ignore[union-attr]
    results = session.exec(statement).all()

    # Calculate balance from splits
    # Logic: For each expense:
    #   - If current user paid: they are owed the sum of all other members' splits
    #   - If someone else paid: current user owes their split amount
    balance = Decimal("0.00")

    # Group splits by expense_id
    expense_splits: dict[int, list[tuple[int, Decimal, int]]] = {}
    for split_row, payer_id in results:
        eid = split_row.expense_id
        if eid not in expense_splits:
            expense_splits[eid] = []
        expense_splits[eid].append((split_row.user_id, split_row.amount, payer_id))

    # Calculate balance for each expense that has splits
    for _eid, splits in expense_splits.items():
        # Find payer for this expense
        payer_id = splits[0][2] if splits else None

        if payer_id == user_id:
            # Current user paid → add amounts owed by others
            for member_id, amount, _ in splits:
                if member_id != user_id:
                    balance += amount
        else:
            # Someone else paid → subtract current user's share
            for member_id, amount, _ in splits:
                if member_id == user_id:
                    balance -= amount

    # Backward compatibility: Handle expenses without split rows (legacy data)
    # Calculate even split (50/50) for these expenses
    expenses_without_splits = (
        select(ExpenseRow)
        .where(
            ExpenseRow.group_id == group_id,
            ExpenseRow.status == ExpenseStatus.PENDING,
            ExpenseRow.status != ExpenseStatus.GIFT,
        )
        .where(ExpenseRow.id.notin_(list(expense_splits.keys()) if expense_splits else [0]))  # ty: ignore[unresolved-attribute]
    )
    if has_filters:
        expenses_without_splits = expenses_without_splits.where(
            ExpenseRow.id.in_(filtered_ids)  # type: ignore[union-attr]
        )
    legacy_expenses = session.exec(expenses_without_splits).all()

    for expense in legacy_expenses:
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
