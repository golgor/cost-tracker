from sqlmodel import Session

from app.adapters.sqlalchemy.group_adapter import SqlAlchemyGroupAdapter
from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter


class _NoOpAuditAdapter:
    """No-op audit adapter used until concrete audit persistence is implemented."""

    def log(self, *args, **kwargs) -> None:
        """Accept audit log calls without persisting anything."""
        return None


class UnitOfWork:
    """Shared SQLAlchemy Session across adapters."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = SqlAlchemyUserAdapter(session)
        self.groups = SqlAlchemyGroupAdapter(session)
        self.audit = _NoOpAuditAdapter()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
