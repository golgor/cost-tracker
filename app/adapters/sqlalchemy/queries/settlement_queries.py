"""Read-only queries for settlement operations."""

from datetime import date
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import ExpenseRow, SettlementExpenseRow, SettlementRow
from app.domain.models import ExpensePublic, ExpenseStatus

if TYPE_CHECKING:
    from app.domain.models import SettlementPublic


def get_unsettled_expenses_grouped(
    session: Session,
    group_id: int,
) -> dict[str, list[ExpensePublic]]:
    """Fetch unsettled expenses grouped by week.

    Returns: {
        "2025-W10": [ExpensePublic, ...],
        "2025-W09": [ExpensePublic, ...],
    }
    """
    statement = (
        select(ExpenseRow)
        .where(ExpenseRow.group_id == group_id)
        .where(ExpenseRow.status != ExpenseStatus.SETTLED)
        .order_by(ExpenseRow.date.desc())  # type: ignore[attr-defined]
    )
    rows = session.exec(statement).all()

    # Group by week
    grouped: dict[str, list[ExpensePublic]] = {}
    for row in rows:
        # Format: "2025-W10" (ISO week format)
        week_key = row.date.strftime("%Y-W%W")
        if week_key not in grouped:
            grouped[week_key] = []
        grouped[week_key].append(_expense_row_to_public(row))

    return grouped


def get_unsettled_count(session: Session, group_id: int) -> int:
    """Count unsettled expenses for dashboard widget."""
    statement = (
        select(ExpenseRow)
        .where(ExpenseRow.group_id == group_id)
        .where(ExpenseRow.status != ExpenseStatus.SETTLED)
    )
    rows = session.exec(statement).all()
    return len(rows)


def get_oldest_unsettled_date(session: Session, group_id: int) -> date | None:
    """Get date of oldest unsettled expense for escalation check."""
    statement = (
        select(ExpenseRow)
        .where(ExpenseRow.group_id == group_id)
        .where(ExpenseRow.status != ExpenseStatus.SETTLED)
        .order_by(ExpenseRow.date.asc())  # type: ignore[attr-defined]
        .limit(1)
    )
    row = session.exec(statement).first()
    return row.date if row else None


def get_settlement_with_expenses(
    session: Session,
    settlement_id: int,
) -> tuple[SettlementPublic, list[ExpensePublic]] | None:
    """Fetch settlement with its linked expenses."""
    from app.adapters.sqlalchemy.settlement_adapter import SqlAlchemySettlementAdapter

    # Get settlement
    settlement_row = session.get(SettlementRow, settlement_id)
    if settlement_row is None:
        return None

    # Get linked expenses
    statement = (
        select(ExpenseRow)
        .join(SettlementExpenseRow)
        .where(SettlementExpenseRow.settlement_id == settlement_id)
        .order_by(ExpenseRow.date.desc())  # type: ignore[attr-defined]
    )
    expense_rows = session.exec(statement).all()

    # Convert to public models
    adapter = SqlAlchemySettlementAdapter(session, None)  # type: ignore[arg-type]
    settlement = adapter._to_public(settlement_row)
    expenses = [_expense_row_to_public(row) for row in expense_rows]

    return settlement, expenses


def _expense_row_to_public(row: ExpenseRow) -> ExpensePublic:
    """Convert ORM row to domain model. Mirrors ExpenseAdapter._to_public()."""
    assert row.id is not None
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
