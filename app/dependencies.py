# Composition root — the ONLY file that wires adapters to domain ports.
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session, create_engine

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.settings import settings

# Database engine (created once at module load)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)


def get_db_session() -> Generator[Session]:
    """Provide a database session."""
    with Session(engine) as session:
        yield session


# Type alias for DB session dependency
DbSession = Annotated[Session, Depends(get_db_session)]


def get_uow(session: DbSession) -> UnitOfWork:
    """Provide a UnitOfWork instance configured for context manager usage.

    Usage in route handlers:
        with uow:
            # Perform operations on uow.users, uow.groups, etc.
            # Transaction automatically commits on success, rolls back on exception

    Session lifecycle is managed by get_db_session() generator.
    UnitOfWork only manages transaction boundaries (commit/rollback).
    """
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
