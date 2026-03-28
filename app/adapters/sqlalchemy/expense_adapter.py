from datetime import date
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import ExpenseNoteRow, ExpenseRow, ExpenseSplitRow
from app.domain.errors import DuplicateBillingPeriodError
from app.domain.models import ExpenseNotePublic, ExpensePublic, ExpenseSplitPublic, SplitType


class SqlAlchemyExpenseAdapter:
    """SQLAlchemy adapter implementing ExpensePort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(
        self,
        expense: ExpensePublic,
    ) -> ExpensePublic:
        """Create a new expense. Returns the persisted expense."""
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
            recurring_definition_id=expense.recurring_definition_id,
            billing_period=expense.billing_period,
            is_auto_generated=expense.is_auto_generated,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            diag = getattr(exc.orig, "diag", None)
            if diag and diag.constraint_name == "uq_expenses_definition_billing_period":
                raise DuplicateBillingPeriodError(
                    definition_id=expense.recurring_definition_id or 0,
                    billing_period=expense.billing_period or "",
                ) from exc
            raise

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
            .order_by(ExpenseRow.date.desc())  # type: ignore
        )
        rows = self._session.exec(statement).all()
        return [self._to_public(row) for row in rows]

    def update(
        self,
        expense_id: int,
        *,
        amount: Decimal | None = None,
        description: str | None = None,
        date: date | None = None,
        payer_id: int | None = None,
        currency: str | None = None,
        split_type: SplitType | None = None,
    ) -> None:
        """Update expense fields. Only provided fields are updated."""
        row = self._session.get(ExpenseRow, expense_id)
        if not row:
            raise ValueError(f"Expense {expense_id} not found")

        # Apply updates
        if amount is not None:
            row.amount = amount
        if description is not None:
            row.description = description
        if date is not None:
            row.date = date
        if payer_id is not None:
            row.payer_id = payer_id
        if currency is not None:
            row.currency = currency
        if split_type is not None:
            row.split_type = split_type

        self._session.add(row)
        self._session.flush()

    def delete(self, expense_id: int) -> None:
        """Delete an expense."""
        row = self._session.get(ExpenseRow, expense_id)
        if not row:
            raise ValueError(f"Expense {expense_id} not found")

        self._session.delete(row)
        self._session.flush()

    def save_splits(
        self,
        expense_id: int,
        splits: list[ExpenseSplitPublic],
    ) -> list[ExpenseSplitPublic]:
        """Save split rows for an expense. Replaces existing splits."""
        # Delete existing splits
        existing = self._session.exec(
            select(ExpenseSplitRow).where(ExpenseSplitRow.expense_id == expense_id)
        ).all()
        for split_row in existing:
            self._session.delete(split_row)

        # Flush deletes before inserting to avoid unique constraint violations
        if existing:
            self._session.flush()

        # Create new splits
        new_rows: list[ExpenseSplitRow] = []
        for split in splits:
            row = ExpenseSplitRow(
                expense_id=expense_id,
                user_id=split.user_id,
                amount=split.amount,
                share_value=split.share_value,
            )
            self._session.add(row)
            new_rows.append(row)

        self._session.flush()

        return [self._split_to_public(row) for row in new_rows]

    def get_splits(self, expense_id: int) -> list[ExpenseSplitPublic]:
        """Get all split rows for an expense."""
        rows = self._session.exec(
            select(ExpenseSplitRow).where(ExpenseSplitRow.expense_id == expense_id)
        ).all()
        return [self._split_to_public(row) for row in rows]

    def _to_public(self, row: ExpenseRow) -> ExpensePublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        if row.id is None:
            raise RuntimeError("Row ID must not be None for persisted rows")
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
            recurring_definition_id=row.recurring_definition_id,
            billing_period=row.billing_period,
            is_auto_generated=row.is_auto_generated,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _split_to_public(self, row: ExpenseSplitRow) -> ExpenseSplitPublic:
        """Convert split ORM row to public domain model."""
        if row.id is None:
            raise RuntimeError("Row ID must not be None for persisted rows")
        return ExpenseSplitPublic(
            id=row.id,
            expense_id=row.expense_id,
            user_id=row.user_id,
            amount=row.amount,
            share_value=row.share_value,
            created_at=row.created_at,
        )

    def save_note(
        self,
        note: ExpenseNotePublic,
    ) -> ExpenseNotePublic:
        """Create a new note for an expense."""
        row = ExpenseNoteRow(
            expense_id=note.expense_id,
            author_id=note.author_id,
            content=note.content,
        )
        self._session.add(row)
        self._session.flush()

        return self._note_to_public(row)

    def update_note(
        self,
        note_id: int,
        content: str,
    ) -> ExpenseNotePublic:
        """Update note content. Only author can edit."""
        row = self._session.exec(select(ExpenseNoteRow).where(ExpenseNoteRow.id == note_id)).first()

        if row is None:
            raise ValueError(f"Note {note_id} not found")

        row.content = content
        self._session.flush()

        return self._note_to_public(row)

    def delete_note(self, note_id: int) -> None:
        """Delete a note. Only author can delete."""
        row = self._session.exec(select(ExpenseNoteRow).where(ExpenseNoteRow.id == note_id)).first()

        if row is None:
            raise ValueError(f"Note {note_id} not found")

        self._session.delete(row)
        self._session.flush()

    def get_note_by_id(self, note_id: int) -> ExpenseNotePublic | None:
        """Retrieve note by database ID."""
        row = self._session.exec(select(ExpenseNoteRow).where(ExpenseNoteRow.id == note_id)).first()

        if row is None:
            return None

        return self._note_to_public(row)

    def list_notes_by_expense(self, expense_id: int) -> list[ExpenseNotePublic]:
        """List all notes for an expense, oldest first."""
        rows = self._session.exec(
            select(ExpenseNoteRow)
            .where(ExpenseNoteRow.expense_id == expense_id)
            .order_by(ExpenseNoteRow.created_at)  # ty: ignore[invalid-argument-type]
        ).all()

        return [self._note_to_public(row) for row in rows]

    def _note_to_public(self, row: ExpenseNoteRow) -> ExpenseNotePublic:
        """Convert note ORM row to public domain model."""
        if row.id is None:
            raise RuntimeError("Row ID must not be None for persisted rows")
        return ExpenseNotePublic(
            id=row.id,
            expense_id=row.expense_id,
            author_id=row.author_id,
            content=row.content,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
