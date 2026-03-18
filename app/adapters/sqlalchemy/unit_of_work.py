import logging
from typing import Any

from sqlmodel import Session

from app.adapters.sqlalchemy.audit_adapter import SqlAlchemyAuditAdapter
from app.adapters.sqlalchemy.group_adapter import SqlAlchemyGroupAdapter
from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter

logger = logging.getLogger(__name__)


class UnitOfWork:
    """Shared SQLAlchemy Session across adapters with context manager support.

    Usage:
        with uow:
            user = uow.users.save(...)
            group = uow.groups.save(...)
        # Automatically commits on success, rolls back on exception

    Note: UnitOfWork context managers cannot be nested.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit = SqlAlchemyAuditAdapter(session)
        self.users = SqlAlchemyUserAdapter(session, self.audit)
        self.groups = SqlAlchemyGroupAdapter(session, self.audit)

    def __enter__(self) -> "UnitOfWork":
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
