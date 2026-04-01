import logging
from typing import Any

from sqlmodel import Session

from app.adapters.sqlalchemy.expense_adapter import SqlAlchemyExpenseAdapter
from app.adapters.sqlalchemy.recurring_adapter import SqlAlchemyRecurringDefinitionAdapter
from app.adapters.sqlalchemy.settlement_adapter import SqlAlchemySettlementAdapter
from app.adapters.sqlalchemy.trip_adapter import SqlAlchemyGuestAdapter, SqlAlchemyTripAdapter
from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter

logger = logging.getLogger(__name__)


class UnitOfWork:
    """Shared SQLAlchemy Session across adapters with context manager support.

    Usage:
        # Mutations: use context manager for commit/rollback
        with uow:
            uow.users.save(...)
            uow.expenses.save(...)
        # Automatically commits on success, rolls back on exception

        # Read-only: no context manager needed (session lifecycle managed by DI)
        # The get_db_session() dependency manages session open/close,
        # so reads can call adapter methods directly without ``with uow:``.
        user = uow.users.get_by_id(user_id)

    Note: UnitOfWork context managers cannot be nested.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = SqlAlchemyUserAdapter(session)
        self.expenses = SqlAlchemyExpenseAdapter(session)
        self.settlements = SqlAlchemySettlementAdapter(session)
        self.recurring = SqlAlchemyRecurringDefinitionAdapter(session)
        self.trips = SqlAlchemyTripAdapter(session)
        self.guests = SqlAlchemyGuestAdapter(session)

    def __enter__(self) -> UnitOfWork:
        """Enter context manager - return self for use in with block."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit context manager - commit on success, rollback on exception.

        Args:
            exc_type: Exception class (None if no exception)
            exc_val: Exception instance (None if no exception)
            exc_tb: Traceback object (None if no exception)

        Returns:
            False - do not suppress exceptions
        """
        if exc_type is not None:
            # Exception occurred - rollback
            try:
                self.session.rollback()
            except Exception:
                logger.exception("Rollback failed during exception handling")
        else:
            # No exception - commit
            self.session.commit()

        # Never suppress exceptions (return False)
        return False
