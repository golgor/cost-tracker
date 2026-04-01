from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import GuestRow, TripExpenseRow, TripParticipantRow, TripRow
from app.domain.models import (
    GuestBase,
    GuestPublic,
    TripBase,
    TripExpenseBase,
    TripExpensePublic,
    TripPublic,
)


class SqlAlchemyGuestAdapter:
    """SQLAlchemy adapter implementing GuestPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, guest: GuestBase) -> GuestPublic:
        row = GuestRow(**guest.model_dump())
        self._session.add(row)
        self._session.flush()
        return self._to_public(row)

    def get_by_id(self, guest_id: int) -> GuestPublic | None:
        row = self._session.get(GuestRow, guest_id)
        if not row:
            return None
        return self._to_public(row)

    def get_by_user_id(self, user_id: int) -> GuestPublic | None:
        statement = select(GuestRow).where(GuestRow.user_id == user_id)
        row = self._session.exec(statement).first()
        if not row:
            return None
        return self._to_public(row)

    def list_all(self) -> list[GuestPublic]:
        rows = self._session.exec(select(GuestRow)).all()
        return [self._to_public(r) for r in rows]

    def _to_public(self, row: GuestRow) -> GuestPublic:
        if row.id is None:
            raise RuntimeError("Row ID must not be None for persisted rows")
        return GuestPublic(id=row.id, name=row.name, user_id=row.user_id)


class SqlAlchemyTripAdapter:
    """SQLAlchemy adapter implementing TripPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, trip: TripBase) -> TripPublic:
        row = TripRow(**trip.model_dump())
        self._session.add(row)
        self._session.flush()
        return self._to_public(row)

    def get_by_id(self, trip_id: int) -> TripPublic | None:
        row = self._session.get(TripRow, trip_id)
        return self._to_public(row) if row else None

    def get_by_sharing_token(self, token: str) -> TripPublic | None:
        statement = select(TripRow).where(TripRow.sharing_token == token)
        row = self._session.exec(statement).first()
        return self._to_public(row) if row else None

    def list_all(self) -> list[TripPublic]:
        statement = select(TripRow).order_by(TripRow.created_at.desc())
        rows = self._session.exec(statement).all()
        return [self._to_public(r) for r in rows]

    def update(
        self,
        trip_id: int,
        *,
        name: str | None = None,
        currency: str | None = None,
        is_active: bool | None = None,
    ) -> TripPublic:
        row = self._session.get(TripRow, trip_id)
        if not row:
            raise ValueError(f"Trip {trip_id} not found")
        if name is not None:
            row.name = name
        if currency is not None:
            row.currency = currency
        if is_active is not None:
            row.is_active = is_active
        self._session.add(row)
        self._session.flush()
        return self._to_public(row)

    def delete(self, trip_id: int) -> None:
        row = self._session.get(TripRow, trip_id)
        if row:
            self._session.delete(row)
            self._session.flush()

    def add_participants(self, trip_id: int, guest_ids: list[int]) -> None:
        statement = select(TripParticipantRow.guest_id).where(TripParticipantRow.trip_id == trip_id)
        existing = set(self._session.exec(statement).all())
        for gid in guest_ids:
            if gid not in existing:
                self._session.add(TripParticipantRow(trip_id=trip_id, guest_id=gid))
        self._session.flush()

    def get_participants(self, trip_id: int) -> list[GuestPublic]:
        statement = (
            select(GuestRow)
            .join(TripParticipantRow, TripParticipantRow.guest_id == GuestRow.id)
            .where(TripParticipantRow.trip_id == trip_id)
        )
        rows = self._session.exec(statement).all()
        return [GuestPublic(id=r.id, name=r.name, user_id=r.user_id) for r in rows]

    def remove_participant(self, trip_id: int, guest_id: int) -> None:
        statement = select(TripParticipantRow).where(
            TripParticipantRow.trip_id == trip_id, TripParticipantRow.guest_id == guest_id
        )
        row = self._session.exec(statement).first()
        if row:
            self._session.delete(row)
            self._session.flush()

    def save_expense(self, expense: TripExpenseBase) -> TripExpensePublic:
        row = TripExpenseRow(**expense.model_dump())
        self._session.add(row)
        self._session.flush()
        return self._expense_to_public(row)

    def get_expense_by_id(self, expense_id: int) -> TripExpensePublic | None:
        row = self._session.get(TripExpenseRow, expense_id)
        return self._expense_to_public(row) if row else None

    def list_expenses(self, trip_id: int) -> list[TripExpensePublic]:
        # Ordered newest first
        statement = (
            select(TripExpenseRow)
            .where(TripExpenseRow.trip_id == trip_id)
            .order_by(TripExpenseRow.date.desc())
        )
        rows = self._session.exec(statement).all()
        return [self._expense_to_public(r) for r in rows]

    def update_expense(
        self,
        expense_id: int,
        *,
        description: str | None = None,
        amount: Decimal | None = None,
        expense_date: date | None = None,
        paid_by_id: int | None = None,
    ) -> TripExpensePublic:
        row = self._session.get(TripExpenseRow, expense_id)
        if not row:
            raise ValueError(f"Trip expense {expense_id} not found")
        if description is not None:
            row.description = description
        if amount is not None:
            row.amount = amount
        if expense_date is not None:
            row.date = expense_date
        if paid_by_id is not None:
            row.paid_by_id = paid_by_id
        self._session.add(row)
        self._session.flush()
        return self._expense_to_public(row)

    def delete_expense(self, expense_id: int) -> None:
        row = self._session.get(TripExpenseRow, expense_id)
        if row:
            self._session.delete(row)
            self._session.flush()

    def _to_public(self, row: TripRow) -> TripPublic:
        if row.id is None:
            raise RuntimeError("Row ID must not be None for persisted rows")
        return TripPublic(
            id=row.id,
            name=row.name,
            currency=row.currency,
            sharing_token=row.sharing_token,
            is_active=row.is_active,
            created_by_id=row.created_by_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _expense_to_public(self, row: TripExpenseRow) -> TripExpensePublic:
        if row.id is None:
            raise RuntimeError("Row ID must not be None for persisted rows")
        return TripExpensePublic(
            id=row.id,
            trip_id=row.trip_id,
            description=row.description,
            amount=row.amount,
            date=row.date,
            paid_by_id=row.paid_by_id,
            created_by_guest_id=row.created_by_guest_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
