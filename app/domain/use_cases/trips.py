"""Trip domain use cases."""

import secrets
from datetime import date
from decimal import Decimal

from app.domain.balance import (
    MemberBalance,
    SettlementTransaction,
    calculate_balances_from_splits,
    minimize_transactions,
)
from app.domain.errors import (
    TripAuthorizationError,
    TripExpenseNotFoundError,
    TripNotActiveError,
    TripNotFoundError,
)
from app.domain.models import (
    ExpensePublic,
    ExpenseStatus,
    GuestBase,
    GuestPublic,
    SplitType,
    TripBase,
    TripExpenseBase,
    TripExpensePublic,
    TripPublic,
)
from app.domain.ports import UNSET, UnitOfWorkPort, Unset, UpdateValue


def _get_trip_or_raise(uow: UnitOfWorkPort, trip_id: int) -> TripPublic:
    """Fetch trip by ID or raise TripNotFoundError."""
    trip = uow.trips.get_by_id(trip_id)
    if not trip:
        raise TripNotFoundError(trip_id)
    return trip


def _assert_trip_active(trip: TripPublic) -> None:
    """Raise TripNotActiveError if trip is settled."""
    if not trip.is_active:
        raise TripNotActiveError(trip.id)


def _assert_trip_owner(trip: TripPublic, user_id: int) -> None:
    """Raise TripAuthorizationError if user does not own the trip."""
    if trip.created_by_id != user_id:
        raise TripAuthorizationError()


def create_guest(uow: UnitOfWorkPort, name: str, user_id: int | None = None) -> GuestPublic:
    """Create a new global guest."""
    guest = GuestBase(name=name, user_id=user_id)
    return uow.guests.save(guest)


def get_all_guests(uow: UnitOfWorkPort) -> list[GuestPublic]:
    """Retrieve all global guests."""
    return uow.guests.list_all()


def create_trip(
    uow: UnitOfWorkPort,
    name: str,
    currency: str,
    created_by_id: int,
    participant_ids: list[int],
    description: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> TripPublic:
    """Create a new trip and add its initial participants."""
    token = secrets.token_urlsafe(32)
    trip = TripBase(
        name=name,
        description=description or None,
        currency=currency,
        sharing_token=token,
        is_active=True,
        created_by_id=created_by_id,
        start_date=start_date,
        end_date=end_date,
    )
    saved_trip = uow.trips.save(trip)

    if participant_ids:
        uow.trips.add_participants(saved_trip.id, participant_ids)

    return saved_trip


def get_trip_details(
    uow: UnitOfWorkPort, trip_id: int
) -> tuple[TripPublic, list[GuestPublic], list[TripExpensePublic]]:
    """Load trip along with participants and expenses."""
    trip = _get_trip_or_raise(uow, trip_id)
    participants = uow.trips.get_participants(trip_id)
    expenses = uow.trips.list_expenses(trip_id)
    return trip, participants, expenses


def add_expense(
    uow: UnitOfWorkPort,
    trip_id: int,
    description: str,
    amount: Decimal,
    expense_date: date,
    paid_by_id: int,
    created_by_guest_id: int,
    split_with_ids: list[int] | None = None,
) -> TripExpensePublic:
    """Add a new expense to a trip with even splits among selected participants."""
    trip = _get_trip_or_raise(uow, trip_id)
    _assert_trip_active(trip)

    # Default to all participants if none specified
    if not split_with_ids:
        participants = uow.trips.get_participants(trip_id)
        split_with_ids = [p.id for p in participants]

    expense = TripExpenseBase(
        trip_id=trip_id,
        description=description,
        amount=amount,
        date=expense_date,
        paid_by_id=paid_by_id,
        created_by_guest_id=created_by_guest_id,
    )
    saved = uow.trips.save_expense(expense)

    # Save even splits among selected participants
    num = len(split_with_ids)
    if num > 0:
        per_person = round(amount / num, 2)
        remainder = amount - (per_person * num)
        for i, pid in enumerate(split_with_ids):
            share = per_person + (remainder if i == 0 else Decimal("0"))
            uow.trips.save_expense_split(saved.id, pid, share)

    return saved


def update_expense(
    uow: UnitOfWorkPort,
    trip_id: int,
    expense_id: int,
    user_id: int,
    *,
    description: str | None = None,
    amount: Decimal | None = None,
    expense_date: date | None = None,
    paid_by_id: int | None = None,
) -> TripExpensePublic:
    """Update a trip expense (admin only)."""
    trip = _get_trip_or_raise(uow, trip_id)
    _assert_trip_owner(trip, user_id)
    _assert_trip_active(trip)

    existing = uow.trips.get_expense_by_id(expense_id)
    if not existing or existing.trip_id != trip_id:
        raise TripExpenseNotFoundError(expense_id)

    return uow.trips.update_expense(
        expense_id,
        description=description,
        amount=amount,
        expense_date=expense_date,
        paid_by_id=paid_by_id,
    )


def delete_expense(
    uow: UnitOfWorkPort,
    trip_id: int,
    expense_id: int,
    user_id: int,
) -> None:
    """Delete a trip expense (admin only)."""
    trip = _get_trip_or_raise(uow, trip_id)
    _assert_trip_owner(trip, user_id)
    _assert_trip_active(trip)

    existing = uow.trips.get_expense_by_id(expense_id)
    if not existing or existing.trip_id != trip_id:
        raise TripExpenseNotFoundError(expense_id)

    uow.trips.delete_expense(expense_id)


def update_trip(
    uow: UnitOfWorkPort,
    trip_id: int,
    user_id: int,
    *,
    name: str | None = None,
    description: UpdateValue[str | None] = UNSET,
    currency: str | None = None,
    start_date: UpdateValue[date | None] = UNSET,
    end_date: UpdateValue[date | None] = UNSET,
) -> TripPublic:
    """Update trip details (admin only)."""
    trip = _get_trip_or_raise(uow, trip_id)
    _assert_trip_owner(trip, user_id)
    kwargs: dict = {"name": name, "currency": currency}
    if not isinstance(description, Unset):
        kwargs["description"] = description
    if not isinstance(start_date, Unset):
        kwargs["start_date"] = start_date
    if not isinstance(end_date, Unset):
        kwargs["end_date"] = end_date
    return uow.trips.update(trip_id, **kwargs)


def settle_trip(uow: UnitOfWorkPort, trip_id: int, user_id: int) -> TripPublic:
    """Mark a trip as settled, locking it from further changes."""
    trip = _get_trip_or_raise(uow, trip_id)
    _assert_trip_owner(trip, user_id)
    return uow.trips.update(trip_id, is_active=False)


def delete_trip(uow: UnitOfWorkPort, trip_id: int, user_id: int) -> None:
    """Delete a trip entirely (admin only)."""
    trip = _get_trip_or_raise(uow, trip_id)
    _assert_trip_owner(trip, user_id)
    uow.trips.delete(trip_id)


def add_participant(uow: UnitOfWorkPort, trip_id: int, user_id: int, guest_ids: list[int]) -> None:
    """Add participants to a trip (admin only)."""
    trip = _get_trip_or_raise(uow, trip_id)
    _assert_trip_owner(trip, user_id)
    _assert_trip_active(trip)
    uow.trips.add_participants(trip_id, guest_ids)


def remove_participant(uow: UnitOfWorkPort, trip_id: int, user_id: int, guest_id: int) -> None:
    """Remove a participant from a trip (admin only)."""
    trip = _get_trip_or_raise(uow, trip_id)
    _assert_trip_owner(trip, user_id)
    _assert_trip_active(trip)
    uow.trips.remove_participant(trip_id, guest_id)


def calculate_trip_settlement(
    uow: UnitOfWorkPort, trip_id: int
) -> tuple[list[SettlementTransaction], dict[int, MemberBalance]]:
    """
    Calculate the minimal network of transactions to settle the trip.

    Maps TripExpense models into the expected ExpensePublic interface
    so that balance.py can optimize them transparently using Guest IDs.
    """
    trip = _get_trip_or_raise(uow, trip_id)

    participants = uow.trips.get_participants(trip_id)
    member_ids = [p.id for p in participants]

    trip_expenses = uow.trips.list_expenses(trip_id)

    expenses: list[ExpensePublic] = []
    splits_by_expense: dict[int, list[tuple[int, Decimal]]] = {}

    for tx in trip_expenses:
        exp = ExpensePublic(
            id=tx.id,
            amount=tx.amount,
            description=tx.description,
            date=tx.date,
            creator_id=tx.created_by_guest_id,
            payer_id=tx.paid_by_id,
            currency=trip.currency,
            status=ExpenseStatus.PENDING,
            created_at=tx.created_at,
            updated_at=tx.updated_at,
            split_type=SplitType.EVEN,
        )
        expenses.append(exp)

        # Use stored splits if available, otherwise fall back to even split
        stored_splits = uow.trips.list_expense_splits(tx.id)
        if stored_splits:
            splits_by_expense[tx.id] = [(s.guest_id, s.amount) for s in stored_splits]
        else:
            # Backward compat: even split among all participants
            splits: list[tuple[int, Decimal]] = []
            num_participants = len(member_ids)
            if num_participants == 0:
                continue

            amount_per_person = round(tx.amount / num_participants, 2)
            remainder = tx.amount - (amount_per_person * num_participants)

            for i, pid in enumerate(member_ids):
                share = amount_per_person
                if i == 0:
                    share += remainder
                splits.append((pid, share))

            splits_by_expense[tx.id] = splits

    balances = calculate_balances_from_splits(expenses, splits_by_expense, member_ids)
    transactions = minimize_transactions(balances)

    return transactions, balances
