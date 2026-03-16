# Composition root — the ONLY file that wires adapters to domain ports.
from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, create_engine

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import decode_session
from app.settings import settings

# Database engine (created once at module load)
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


def get_db_session() -> Generator[Session, None, None]:
    """Provide a database session."""
    with Session(engine) as session:
        yield session


def get_uow(session: Session = Depends(get_db_session)) -> UnitOfWork:
    """Provide a UnitOfWork instance."""
    return UnitOfWork(session)


def get_current_user_id(request: Request) -> int:
    """Extract authenticated user_id from request state (set by AuthMiddleware)."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def get_optional_user_id(request: Request) -> int | None:
    """Like get_current_user_id but returns None instead of raising."""
    return getattr(request.state, "user_id", None)
