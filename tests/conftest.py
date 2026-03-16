"""Test fixtures for unit tests (SQLite in-memory) and optional integration tests (PostgreSQL)."""

import os

# Set test environment variables BEFORE any app imports (pydantic-settings reads at import time)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("OIDC_ISSUER", "https://test.example.com")
os.environ.setdefault("OIDC_CLIENT_ID", "test-client")
os.environ.setdefault("OIDC_CLIENT_SECRET", "test-secret")
os.environ.setdefault("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback")
os.environ.setdefault("ENV", "dev")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlmodel import SQLModel

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork

# ---------------------------------------------------------------------------
# SQLite in-memory engine — used for all unit tests (fast, isolated)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine) -> Session:
    """Provide a transactional SQLite session, rolled back after each test."""
    connection = sqlite_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def uow(db_session) -> UnitOfWork:
    """Provide a UnitOfWork backed by the SQLite test session."""
    return UnitOfWork(session=db_session)


# ---------------------------------------------------------------------------
# PostgreSQL fixtures — gated by TEST_DATABASE_URL env var (CI-only by default)
# Run locally: TEST_DATABASE_URL=postgresql://... mise run test:integration
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def pg_engine():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set — skipping PostgreSQL integration test")
    engine = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine) -> Session:
    """Provide a transactional PostgreSQL session, rolled back after each test."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def pg_uow(pg_session) -> UnitOfWork:
    """Provide a UnitOfWork backed by the PostgreSQL test session."""
    return UnitOfWork(session=pg_session)
