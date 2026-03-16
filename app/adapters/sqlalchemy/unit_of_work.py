from sqlmodel import Session

from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter


class UnitOfWork:
    """Shared SQLAlchemy Session across adapters."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = SqlAlchemyUserAdapter(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
