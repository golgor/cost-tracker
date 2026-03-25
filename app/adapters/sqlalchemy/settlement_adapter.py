from sqlmodel import Session, select

from app.adapters.sqlalchemy.audit_adapter import SqlAlchemyAuditAdapter
from app.adapters.sqlalchemy.changes import snapshot_new
from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    SettlementExpenseRow,
    SettlementRow,
)
from app.domain.models import ExpenseStatus, SettlementPublic


class SqlAlchemySettlementAdapter:
    """SQLAlchemy adapter implementing SettlementPort."""

    def __init__(self, session: Session, audit: SqlAlchemyAuditAdapter) -> None:
        self._session = session
        self._audit = audit

    def save(
        self,
        settlement: SettlementPublic,
        expense_ids: list[int],
        *,
        actor_id: int,
    ) -> SettlementPublic:
        """Create a new settlement with linked expenses. Auto-audits."""
        # Create settlement row
        row = SettlementRow(
            group_id=settlement.group_id,
            reference_id=settlement.reference_id,
            settled_by_id=settlement.settled_by_id,
            total_amount=settlement.total_amount,
            transfer_from_user_id=settlement.transfer_from_user_id,
            transfer_to_user_id=settlement.transfer_to_user_id,
            settled_at=settlement.settled_at,
        )

        changes = snapshot_new(row, exclude={"id", "created_at"})
        self._session.add(row)
        self._session.flush()

        assert row.id is not None  # guaranteed after flush
        settlement_id = row.id

        # Link expenses to settlement
        for expense_id in expense_ids:
            link = SettlementExpenseRow(
                settlement_id=settlement_id,
                expense_id=expense_id,
            )
            self._session.add(link)

        # Update expense statuses to SETTLED
        for expense_id in expense_ids:
            expense_row = self._session.get(ExpenseRow, expense_id)
            assert expense_row is not None
            expense_row.status = ExpenseStatus.SETTLED

        self._session.flush()

        # Audit log
        changes["expense_ids"] = {"old": None, "new": expense_ids}
        self._audit.log(
            action="settlement_confirmed",
            actor_id=actor_id,
            entity_type="settlement",
            entity_id=settlement_id,
            changes=changes,
        )

        return self._to_public(row)

    def get_by_id(self, settlement_id: int) -> SettlementPublic | None:
        """Retrieve settlement by database ID."""
        row = self._session.get(SettlementRow, settlement_id)
        if row is None:
            return None
        return self._to_public(row)

    def list_by_group(self, group_id: int, limit: int = 100) -> list[SettlementPublic]:
        """List settlements for a group, newest first."""
        statement = (
            select(SettlementRow)
            .where(SettlementRow.group_id == group_id)
            .order_by(SettlementRow.settled_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        )
        rows = self._session.exec(statement).all()
        return [self._to_public(row) for row in rows]

    def get_expense_ids(self, settlement_id: int) -> list[int]:
        """Get expense IDs linked to a settlement."""
        statement = select(SettlementExpenseRow.expense_id).where(
            SettlementExpenseRow.settlement_id == settlement_id
        )
        rows = self._session.exec(statement).all()
        return list(rows)

    def _to_public(self, row: SettlementRow) -> SettlementPublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        assert row.id is not None
        assert row.created_at is not None

        return SettlementPublic(
            id=row.id,
            group_id=row.group_id,
            reference_id=row.reference_id,
            settled_by_id=row.settled_by_id,
            total_amount=row.total_amount,
            transfer_from_user_id=row.transfer_from_user_id,
            transfer_to_user_id=row.transfer_to_user_id,
            settled_at=row.settled_at,
            created_at=row.created_at,
        )
