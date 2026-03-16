# Skeleton — UnitOfWork will be expanded in Stories 1.5, 2.1+
from sqlalchemy.orm import Session


class UnitOfWork:
    """Shared SQLAlchemy Session across adapters. Skeleton for now."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
