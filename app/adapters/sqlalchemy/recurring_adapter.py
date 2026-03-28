"""SQLAlchemy adapter for RecurringDefinition persistence."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import RecurringDefinitionRow
from app.domain.errors import RecurringDefinitionNotFoundError
from app.domain.models import (
    RecurringDefinitionBase,
    RecurringDefinitionPublic,
    RecurringFrequency,
    SplitType,
)


class SqlAlchemyRecurringDefinitionAdapter:
    """SQLAlchemy adapter implementing RecurringDefinitionPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, definition: RecurringDefinitionBase) -> RecurringDefinitionPublic:
        """Create a new recurring definition. Returns the persisted definition."""
        row = RecurringDefinitionRow(
            group_id=definition.group_id,
            name=definition.name,
            amount=definition.amount,
            frequency=definition.frequency,
            interval_months=definition.interval_months,
            next_due_date=definition.next_due_date,
            payer_id=definition.payer_id,
            split_type=definition.split_type,
            split_config=definition.split_config,
            category=definition.category,
            auto_generate=definition.auto_generate,
            is_active=definition.is_active,
            currency=definition.currency,
        )
        self._session.add(row)
        self._session.flush()

        return self._to_public(row)

    def get_by_id(self, definition_id: int) -> RecurringDefinitionPublic | None:
        """Retrieve recurring definition by database ID."""
        row = self._session.get(RecurringDefinitionRow, definition_id)
        if row is None:
            return None
        return self._to_public(row)

    def list_by_group(
        self,
        group_id: int,
        *,
        active_only: bool = False,
        include_deleted: bool = False,
    ) -> list[RecurringDefinitionPublic]:
        """List recurring definitions for a group.

        Excludes soft-deleted rows by default (include_deleted=False).
        """
        statement = select(RecurringDefinitionRow).where(
            RecurringDefinitionRow.group_id == group_id,
        )
        if not include_deleted:
            statement = statement.where(RecurringDefinitionRow.deleted_at.is_(None))  # type: ignore[union-attr]
        if active_only:
            statement = statement.where(RecurringDefinitionRow.is_active.is_(True))  # type: ignore[union-attr]
        statement = statement.order_by(RecurringDefinitionRow.next_due_date)  # type: ignore[arg-type]

        rows = self._session.exec(statement).all()
        return [self._to_public(row) for row in rows]

    def update(
        self,
        definition_id: int,
        *,
        name: str | None = None,
        amount: Decimal | None = None,
        frequency: RecurringFrequency | None = None,
        interval_months: int | None = None,
        next_due_date: date | None = None,
        payer_id: int | None = None,
        split_type: SplitType | None = None,
        split_config: dict | None = None,
        category: str | None = None,
        auto_generate: bool | None = None,
        is_active: bool | None = None,
        currency: str | None = None,
    ) -> RecurringDefinitionPublic:
        """Update recurring definition fields. Only provided fields are updated."""
        row = self._session.get(RecurringDefinitionRow, definition_id)
        if row is None or row.deleted_at is not None:
            raise RecurringDefinitionNotFoundError(
                f"Recurring definition {definition_id} not found"
            )

        if name is not None:
            row.name = name
        if amount is not None:
            row.amount = amount
        if frequency is not None:
            row.frequency = frequency
        if interval_months is not None:
            row.interval_months = interval_months
        if next_due_date is not None:
            row.next_due_date = next_due_date
        if payer_id is not None:
            row.payer_id = payer_id
        if split_type is not None:
            row.split_type = split_type
        if split_config is not None:
            row.split_config = split_config
        if category is not None:
            row.category = category
        if auto_generate is not None:
            row.auto_generate = auto_generate
        if is_active is not None:
            row.is_active = is_active
        if currency is not None:
            row.currency = currency

        self._session.add(row)
        self._session.flush()

        return self._to_public(row)

    def list_overdue_auto(self, current_date: date) -> list[RecurringDefinitionPublic]:
        """Return active auto_generate definitions whose next_due_date <= current_date."""
        statement = (
            select(RecurringDefinitionRow)
            .where(RecurringDefinitionRow.deleted_at.is_(None))  # type: ignore[union-attr]
            .where(RecurringDefinitionRow.is_active.is_(True))  # type: ignore[union-attr]
            .where(RecurringDefinitionRow.auto_generate.is_(True))  # type: ignore[union-attr]
            .where(RecurringDefinitionRow.next_due_date <= current_date)
            .order_by(RecurringDefinitionRow.next_due_date)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
        rows = self._session.exec(statement).all()
        return [self._to_public(row) for row in rows]

    def soft_delete(self, definition_id: int) -> None:
        """Soft-delete a recurring definition by setting deleted_at."""
        row = self._session.get(RecurringDefinitionRow, definition_id)
        if row is None or row.deleted_at is not None:
            raise RecurringDefinitionNotFoundError(
                f"Recurring definition {definition_id} not found"
            )

        row.deleted_at = datetime.now(tz=UTC)
        self._session.add(row)
        self._session.flush()

    def _to_public(self, row: RecurringDefinitionRow) -> RecurringDefinitionPublic:
        """Convert ORM row to public domain model. Row never leaves adapter."""
        if row.id is None:
            raise RuntimeError("Row ID must not be None for persisted rows")
        return RecurringDefinitionPublic(
            id=row.id,
            group_id=row.group_id,
            name=row.name,
            amount=row.amount,
            frequency=row.frequency,
            interval_months=row.interval_months,
            next_due_date=row.next_due_date,
            payer_id=row.payer_id,
            split_type=row.split_type,
            split_config=row.split_config,
            category=row.category,
            auto_generate=row.auto_generate,
            is_active=row.is_active,
            currency=row.currency,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
        )
