from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    SettlementExpenseRow,
    SettlementRow,
    SettlementTransactionRow,
)
from app.adapters.sqlalchemy.queries.mappings import transaction_row_to_public
from app.domain.models import (
    ExpenseStatus,
    SettlementBase,
    SettlementPublic,
    SettlementTransactionBase,
    SettlementTransactionPublic,
)


class SqlAlchemySettlementAdapter:
    """SQLAlchemy adapter implementing SettlementPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        settlement: SettlementBase,
        expense_ids: list[int],
        transactions: list[SettlementTransactionBase],
    ) -> SettlementPublic:
        """Create a new settlement with linked expenses and transactions."""
        row = SettlementRow(
            reference_id=settlement.reference_id,
            settled_by_id=settlement.settled_by_id,
            settled_at=settlement.settled_at,
        )

        self._session.add(row)
        self._session.flush()

        assert row.id is not None
        settlement_id = row.id

        for tx in transactions:
            tx_row = SettlementTransactionRow(
                settlement_id=settlement_id,
                from_user_id=tx.from_user_id,
                to_user_id=tx.to_user_id,
                amount=tx.amount,
            )
            self._session.add(tx_row)

        for expense_id in expense_ids:
            link = SettlementExpenseRow(
                settlement_id=settlement_id,
                expense_id=expense_id,
            )
            self._session.add(link)

        for expense_id in expense_ids:
            expense_row = self._session.get(ExpenseRow, expense_id)
            assert expense_row is not None
            expense_row.status = ExpenseStatus.SETTLED

        self._session.flush()

        return self._to_public(row)

    def get_by_id(self, settlement_id: int) -> SettlementPublic | None:
        """Retrieve settlement by database ID."""
        row = self._session.get(SettlementRow, settlement_id)
        if row is None:
            return None
        return self._to_public(row)

    def list_all(self, limit: int = 100) -> list[SettlementPublic]:
        """List settlements, newest first."""
        statement = select(SettlementRow).order_by(SettlementRow.settled_at.desc()).limit(limit)
        rows = self._session.exec(statement).all()
        return [self._to_public(row) for row in rows]

    def get_expense_ids(self, settlement_id: int) -> list[int]:
        """Get expense IDs linked to a settlement."""
        statement = select(SettlementExpenseRow.expense_id).where(
            SettlementExpenseRow.settlement_id == settlement_id
        )
        rows = self._session.exec(statement).all()
        return list(rows)

    def get_transactions(self, settlement_id: int) -> list[SettlementTransactionPublic]:
        """Get all transactions for a settlement."""
        statement = (
            select(SettlementTransactionRow)
            .where(SettlementTransactionRow.settlement_id == settlement_id)
            .order_by(SettlementTransactionRow.id)  # ty: ignore[invalid-argument-type]
        )
        rows = self._session.exec(statement).all()
        return [transaction_row_to_public(row) for row in rows]

    def reference_exists(self, reference_id: str) -> bool:
        """Check if a reference_id already exists (unbounded query)."""
        statement = select(SettlementRow).where(SettlementRow.reference_id == reference_id)
        result = self._session.exec(statement).first()
        return result is not None

    def _to_public(self, row: SettlementRow) -> SettlementPublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        if row.id is None or row.created_at is None:
            raise RuntimeError("Row ID and created_at must not be None for persisted rows")

        return SettlementPublic(
            id=row.id,
            reference_id=row.reference_id,
            settled_by_id=row.settled_by_id,
            settled_at=row.settled_at,
            created_at=row.created_at,
        )
