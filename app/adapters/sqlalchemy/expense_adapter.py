from sqlmodel import Session, select

from app.adapters.sqlalchemy.audit_adapter import SqlAlchemyAuditAdapter
from app.adapters.sqlalchemy.changes import snapshot_new
from app.adapters.sqlalchemy.orm_models import ExpenseRow
from app.domain.models import ExpensePublic


class SqlAlchemyExpenseAdapter:
    """SQLAlchemy adapter implementing ExpensePort."""

    def __init__(self, session: Session, audit: SqlAlchemyAuditAdapter) -> None:
        self._session = session
        self._audit = audit

    def save(
        self,
        expense: ExpensePublic,
        *,
        actor_id: int,
    ) -> ExpensePublic:
        """Create a new expense. Returns the persisted expense. Auto-audits."""
        row = ExpenseRow(
            group_id=expense.group_id,
            amount=expense.amount,
            description=expense.description,
            date=expense.date,
            creator_id=expense.creator_id,
            payer_id=expense.payer_id,
            currency=expense.currency,
            split_type=expense.split_type,
            status=expense.status,
        )
        changes = snapshot_new(row, exclude={"id", "created_at", "updated_at"})
        self._session.add(row)
        self._session.flush()

        assert row.id is not None  # guaranteed after flush
        self._audit.log(
            action="expense_created",
            actor_id=actor_id,
            entity_type="expense",
            entity_id=row.id,
            changes=changes,
        )
        return self._to_public(row)

    def get_by_id(self, expense_id: int) -> ExpensePublic | None:
        """Retrieve expense by database ID."""
        row = self._session.get(ExpenseRow, expense_id)
        if row is None:
            return None
        return self._to_public(row)

    def list_by_group(self, group_id: int) -> list[ExpensePublic]:
        """List all expenses for a group, ordered by date descending."""
        statement = (
            select(ExpenseRow)
            .where(ExpenseRow.group_id == group_id)
            .order_by(ExpenseRow.date.desc())
        )
        rows = self._session.exec(statement).all()
        return [self._to_public(row) for row in rows]

    def _to_public(self, row: ExpenseRow) -> ExpensePublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        return ExpensePublic(
            id=row.id,  # type: ignore[arg-type]
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
