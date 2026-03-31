# Domain ports (Protocol classes)
# Allowed imports: stdlib + external validation libs (sqlmodel, pydantic) per ADR-011
# Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from app.domain.models import (
    ExpenseBase,
    ExpenseNotePublic,
    ExpensePublic,
    ExpenseSplitPublic,
    GuestBase,
    GuestPublic,
    RecurringDefinitionBase,
    RecurringDefinitionPublic,
    RecurringFrequency,
    SettlementBase,
    SettlementPublic,
    SettlementTransactionBase,
    SettlementTransactionPublic,
    SplitType,
    TripBase,
    TripExpenseBase,
    TripExpensePublic,
    TripPublic,
    UserPublic,
)


class UserPort(Protocol):
    """Port for User persistence operations."""

    def get_by_id(self, user_id: int) -> UserPublic | None:
        """Retrieve user by database ID."""
        ...

    def get_by_ids(self, user_ids: list[int]) -> list[UserPublic]:
        """Retrieve multiple users by their database IDs."""
        ...

    def get_by_oidc_sub(self, oidc_sub: str) -> UserPublic | None:
        """Retrieve user by OIDC subject identifier."""
        ...

    def save(self, oidc_sub: str, email: str, display_name: str) -> UserPublic:
        """Create or update a user. Returns the persisted user."""
        ...

    def count(self) -> int:
        """Count the total number of users."""
        ...

    def get_all(self) -> list[UserPublic]:
        """Get list of all users."""
        ...


class ExpensePort(Protocol):
    """Port for Expense persistence operations."""

    def save(
        self,
        expense: ExpenseBase,
    ) -> ExpensePublic:
        """Create a new expense. Returns the persisted expense."""
        ...

    def get_by_id(self, expense_id: int) -> ExpensePublic | None:
        """Retrieve expense by database ID."""
        ...

    def list_all(self) -> list[ExpensePublic]:
        """List all expenses, ordered by date descending."""
        ...

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
        ...

    def delete(self, expense_id: int) -> None:
        """Delete an expense."""
        ...

    def save_splits(
        self,
        expense_id: int,
        splits: list[ExpenseSplitPublic],
    ) -> list[ExpenseSplitPublic]:
        """Save split rows for an expense. Replaces existing splits."""
        ...

    def get_splits(self, expense_id: int) -> list[ExpenseSplitPublic]:
        """Get all split rows for an expense."""
        ...

    def save_note(self, note: ExpenseNotePublic) -> ExpenseNotePublic:
        """Create a new note for an expense."""
        ...

    def update_note(self, note_id: int, content: str) -> ExpenseNotePublic:
        """Update note content."""
        ...

    def delete_note(self, note_id: int) -> None:
        """Delete a note."""
        ...

    def get_note_by_id(self, note_id: int) -> ExpenseNotePublic | None:
        """Retrieve note by database ID."""
        ...

    def list_notes_by_expense(self, expense_id: int) -> list[ExpenseNotePublic]:
        """List all notes for an expense, oldest first."""
        ...


class SettlementPort(Protocol):
    """Port for settlement persistence operations."""

    def save(
        self,
        settlement: SettlementBase,
        expense_ids: list[int],
        transactions: list[SettlementTransactionBase],
    ) -> SettlementPublic:
        """Create a new settlement with linked expenses and transactions."""
        ...

    def get_by_id(self, settlement_id: int) -> SettlementPublic | None:
        """Retrieve settlement by database ID."""
        ...

    def list_all(
        self,
        limit: int = 100,
    ) -> list[SettlementPublic]:
        """List settlements, newest first."""
        ...

    def reference_exists(self, reference_id: str) -> bool:
        """Check if a reference_id already exists (unbounded query)."""
        ...

    def get_expense_ids(self, settlement_id: int) -> list[int]:
        """Get expense IDs linked to a settlement."""
        ...

    def get_transactions(self, settlement_id: int) -> list[SettlementTransactionPublic]:
        """Get all transactions for a settlement."""
        ...


class RecurringDefinitionPort(Protocol):
    """Port for RecurringDefinition persistence operations."""

    def save(self, definition: RecurringDefinitionBase) -> RecurringDefinitionPublic:
        """Create a new recurring definition. Returns the persisted definition."""
        ...

    def get_by_id(self, definition_id: int) -> RecurringDefinitionPublic | None:
        """Retrieve recurring definition by database ID."""
        ...

    def list_all(
        self,
        *,
        active_only: bool = False,
        include_deleted: bool = False,
    ) -> list[RecurringDefinitionPublic]:
        """List recurring definitions.

        Excludes soft-deleted rows by default (include_deleted=False).
        """
        ...

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
        ...

    def soft_delete(self, definition_id: int) -> None:
        """Soft-delete a recurring definition by setting deleted_at."""
        ...

    def list_overdue_auto(self, current_date: date) -> list[RecurringDefinitionPublic]:
        """Return active auto_generate definitions whose next_due_date <= current_date.

        Excludes soft-deleted and paused definitions.
        Ordered by next_due_date ascending (oldest first).
        """
        ...


class GuestPort(Protocol):
    """Port for Global Address Book Guest persistence."""

    def save(self, guest: GuestBase) -> GuestPublic: ...
    def get_by_id(self, guest_id: int) -> GuestPublic | None: ...
    def get_by_user_id(self, user_id: int) -> GuestPublic | None: ...
    def list_all(self) -> list[GuestPublic]: ...


class TripPort(Protocol):
    """Port for Trips persistence."""

    def save(self, trip: TripBase) -> TripPublic: ...
    def get_by_id(self, trip_id: int) -> TripPublic | None: ...
    def get_by_sharing_token(self, token: str) -> TripPublic | None: ...
    def list_all(self) -> list[TripPublic]: ...
    def update(
        self, trip_id: int, *, name: str | None = None, is_active: bool | None = None
    ) -> TripPublic: ...

    # Participants
    def add_participants(self, trip_id: int, guest_ids: list[int]) -> None: ...
    def get_participants(self, trip_id: int) -> list[GuestPublic]: ...
    def remove_participant(self, trip_id: int, guest_id: int) -> None: ...

    # Expenses
    def save_expense(self, expense: TripExpenseBase) -> TripExpensePublic: ...
    def get_expense_by_id(self, expense_id: int) -> TripExpensePublic | None: ...
    def list_expenses(self, trip_id: int) -> list[TripExpensePublic]: ...
    def delete_expense(self, expense_id: int) -> None: ...


class UnitOfWorkPort(Protocol):
    """Port for unit of work pattern with context manager support.

    Provides coordinated access to multiple adapters within a transaction boundary.
    Usage:
        with uow:
            user = uow.users.save(...)
            expense = uow.expenses.save(...)
        # Transaction commits on success or rolls back on exception
    """

    users: UserPort
    expenses: ExpensePort
    settlements: SettlementPort
    recurring: RecurringDefinitionPort
    trips: TripPort
    guests: GuestPort

    def __enter__(self) -> UnitOfWorkPort:
        """Enter context manager - prepares transaction."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit context manager - commits transaction or rolls back on exception.

        Args:
            exc_type: Exception class (None if no exception)
            exc_val: Exception instance (None if no exception)
            exc_tb: Traceback object (None if no exception)

        Returns:
            False - never suppress exceptions
        """
        ...
