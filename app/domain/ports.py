# Domain ports (Protocol classes)
# Allowed imports: stdlib + external validation libs (sqlmodel, pydantic) per ADR-011
# Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
from typing import Any, Protocol  # noqa: F401

from app.domain.models import (
    ExpensePublic,
    GroupPublic,
    MemberRole,
    MembershipPublic,
    SettlementPublic,
    SettlementTransactionPublic,
    SplitType,
    UserPublic,
)


class AuditPort(Protocol):
    """Port for audit log persistence."""

    def log(
        self,
        *,
        action: str,
        actor_id: int,
        entity_type: str,
        entity_id: int,
        changes: dict[str, Any] | None = None,
    ) -> None:
        """Persist an audit log entry. Must share the same transaction as business changes."""
        ...


class UserPort(Protocol):
    """Port for User persistence operations."""

    def get_by_id(self, user_id: int) -> UserPublic | None:
        """Retrieve user by database ID."""
        ...

    def get_by_oidc_sub(self, oidc_sub: str) -> UserPublic | None:
        """Retrieve user by OIDC subject identifier."""
        ...

    def save(self, oidc_sub: str, email: str, display_name: str, *, actor_id: int) -> UserPublic:
        """Create or update a user. Returns the persisted user. Auto-audits."""
        ...

    def promote_to_admin(self, user_id: int, *, actor_id: int) -> UserPublic:
        """Promote user to admin role. Auto-audits."""
        ...

    def demote_to_user(self, user_id: int, *, actor_id: int) -> UserPublic:
        """Demote user to regular user role. Auto-audits."""
        ...

    def deactivate(self, user_id: int, *, actor_id: int) -> UserPublic:
        """Deactivate a user. Auto-audits."""
        ...

    def reactivate(self, user_id: int, *, actor_id: int) -> UserPublic:
        """Reactivate a deactivated user. Auto-audits."""
        ...

    def count_active_admins(self) -> int:
        """Count the number of active admin users."""
        ...

    def get_active_admins(self) -> list[UserPublic]:
        """Get list of all active admin users."""
        ...


class GroupPort(Protocol):
    """Port for Group persistence operations."""

    def get_by_id(self, group_id: int) -> GroupPublic | None:
        """Retrieve group by database ID."""
        ...

    def get_by_user_id(self, user_id: int) -> GroupPublic | None:
        """Retrieve group that user belongs to (MVP1: single household)."""
        ...

    def get_default_group(self) -> GroupPublic | None:
        """Get the default/only household group (MVP1: single household)."""
        ...

    def save(
        self,
        name: str,
        *,
        actor_id: int,
        default_currency: str = "EUR",
        default_split_type: SplitType = SplitType.EVEN,
        tracking_threshold: int = 30,
    ) -> GroupPublic:
        """Create a new group. Returns the persisted group. Auto-audits."""
        ...

    def update(
        self,
        group_id: int,
        *,
        actor_id: int,
        name: str | None = None,
        default_currency: str | None = None,
        default_split_type: SplitType | None = None,
        tracking_threshold: int | None = None,
    ) -> GroupPublic:
        """Update group configuration. Returns the updated group. Auto-audits."""
        ...

    def add_member(
        self,
        group_id: int,
        user_id: int,
        role: MemberRole,
        *,
        actor_id: int,
    ) -> MembershipPublic:
        """Add a user to a group with specified role. Auto-audits."""
        ...

    def get_membership(self, user_id: int, group_id: int) -> MembershipPublic | None:
        """Get membership for a specific user and group."""
        ...

    def get_member_role(self, user_id: int, group_id: int) -> MemberRole | None:
        """Get a user's role within a specific group."""
        ...

    def has_active_admin(self) -> bool:
        """Check if any active admin exists in the system (admin bootstrap trigger)."""
        ...


class ExpensePort(Protocol):
    """Port for Expense persistence operations."""

    def save(
        self,
        expense: ExpensePublic,
        *,
        actor_id: int,
    ) -> ExpensePublic:
        """Create a new expense. Returns the persisted expense. Auto-audits."""
        ...

    def get_by_id(self, expense_id: int) -> ExpensePublic | None:
        """Retrieve expense by database ID."""
        ...

    def list_by_group(self, group_id: int) -> list[ExpensePublic]:
        """List all expenses for a group, ordered by date descending."""
        ...

    def update(
        self,
        expense_id: int,
        *,
        actor_id: int,
        amount: Any | None = None,
        description: str | None = None,
        date: Any | None = None,
        payer_id: int | None = None,
        currency: str | None = None,
    ) -> None:
        """Update expense fields. Only provided fields are updated. Auto-audits."""
        ...

    def delete(self, expense_id: int, *, actor_id: int) -> None:
        """Delete an expense. Auto-audits the deletion with pre-delete snapshot."""
        ...


class SettlementPort(Protocol):
    """Port for settlement persistence operations."""

    def save(
        self,
        settlement: SettlementPublic,
        expense_ids: list[int],
        transactions: list[SettlementTransactionPublic],
        *,
        actor_id: int,
    ) -> SettlementPublic:
        """Create a new settlement with linked expenses and transactions. Auto-audits."""
        ...

    def get_by_id(self, settlement_id: int) -> SettlementPublic | None:
        """Retrieve settlement by database ID."""
        ...

    def list_by_group(
        self,
        group_id: int,
        limit: int = 100,
    ) -> list[SettlementPublic]:
        """List settlements for a group, newest first."""
        ...

    def reference_exists(self, group_id: int, reference_id: str) -> bool:
        """Check if a reference_id already exists for the group (unbounded query)."""
        ...

    def get_expense_ids(self, settlement_id: int) -> list[int]:
        """Get expense IDs linked to a settlement."""
        ...

    def get_transactions(self, settlement_id: int) -> list[SettlementTransactionPublic]:
        """Get all transactions for a settlement."""
        ...


class UnitOfWorkPort(Protocol):
    """Port for unit of work pattern with context manager support.

    Provides coordinated access to multiple adapters within a transaction boundary.
    Usage:
        with uow:
            user = uow.users.save(...)
            group = uow.groups.save(...)
        # Transaction commits on success or rolls back on exception
    """

    users: UserPort
    groups: GroupPort
    expenses: ExpensePort
    audit: AuditPort
    settlements: SettlementPort

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
