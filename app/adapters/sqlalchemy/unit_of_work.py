from sqlmodel import Session

from app.adapters.sqlalchemy.audit_adapter import SqlAlchemyAuditAdapter
from app.adapters.sqlalchemy.group_adapter import SqlAlchemyGroupAdapter
from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter


class UnitOfWork:
    """Shared SQLAlchemy Session across adapters."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit = SqlAlchemyAuditAdapter(session)
        self.users = SqlAlchemyUserAdapter(session, self.audit)
        self.groups = SqlAlchemyGroupAdapter(session, self.audit)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
