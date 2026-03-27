"""Test fixtures using PostgreSQL with _test database suffix.

PostgreSQL-only approach - no SQLite.
See: docs/testing-strategy.md
"""

import os
from collections.abc import Generator
from urllib.parse import urlparse

# Set test environment variables BEFORE any app imports (pydantic-settings reads at import time)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("OIDC_ISSUER", "https://test.example.com")
os.environ.setdefault("OIDC_CLIENT_ID", "test-client")
os.environ.setdefault("OIDC_CLIENT_SECRET", "test-secret")
os.environ.setdefault("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback")
os.environ.setdefault("ENV", "dev")

import pytest
from sqlalchemy import create_engine, text
from sqlmodel import Session, SQLModel

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork


def get_test_database_url() -> str:
    """
    Derive test database URL from DATABASE_URL with _test suffix.

    Example:
        DATABASE_URL=postgresql://user:pass@localhost/costtracker
        -> Test URL=postgresql://user:pass@localhost/costtracker_test
    """
    # Check for explicit override first (CI environments)
    explicit_test_url = os.environ.get("TEST_DATABASE_URL")
    if explicit_test_url:
        return explicit_test_url

    # Import here to avoid circular import issues
    from app.settings import settings

    db_url = str(settings.DATABASE_URL)
    parsed = urlparse(db_url)

    # Replace database name with <name>_test
    original_db = parsed.path.lstrip("/")
    if not original_db:
        raise ValueError("DATABASE_URL has no database name")

    test_db = f"{original_db}_test"

    # Reconstruct URL
    test_url = (
        f"{parsed.scheme}://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/{test_db}"
    )

    return test_url


def create_test_database_if_needed(test_url: str) -> None:
    """Create the test database if it doesn't exist."""
    parsed = urlparse(test_url)
    db_name = parsed.path.lstrip("/")

    # Connect to postgres database to create the test database
    admin_url = (
        f"{parsed.scheme}://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/postgres"
    )

    try:
        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            )
            if not result.scalar():
                # Create the test database
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                print(f"Created test database: {db_name}")
        engine.dispose()
    except Exception as e:
        print(f"Warning: Could not create test database: {e}")
        raise


@pytest.fixture(scope="session")
def db_engine():
    """PostgreSQL engine for tests using _test suffix database."""
    test_url = get_test_database_url()

    # Create test database if needed
    create_test_database_if_needed(test_url)

    # Connect to test database and create tables
    engine = create_engine(test_url)
    SQLModel.metadata.create_all(engine)

    yield engine

    # Cleanup: drop all tables but keep database
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session]:
    """Provide a transactional PostgreSQL session, rolled back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def uow(db_session) -> UnitOfWork:
    """Provide a UnitOfWork backed by the test session."""
    return UnitOfWork(session=db_session)


# Helper functions for tests
def create_test_user(session, oidc_sub: str, email: str, display_name: str | None = None):
    """Create a test user directly in the database."""
    from app.adapters.sqlalchemy.orm_models import UserRow
    from app.domain.models import UserRole

    user = UserRow(
        oidc_sub=oidc_sub,
        email=email,
        display_name=display_name or email.split("@")[0],
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def create_test_group(session, user_id: int, name: str = "Test Group"):
    """Create a test group with the user as admin member."""
    from app.adapters.sqlalchemy.orm_models import GroupRow, MembershipRow
    from app.domain.models import MemberRole, SplitType

    group = GroupRow(
        name=name,
        default_currency="EUR",
        default_split_type=SplitType.EVEN,
        tracking_threshold=30,
    )
    session.add(group)
    session.flush()

    assert group.id is not None  # guaranteed after flush
    membership = MembershipRow(
        group_id=group.id,
        user_id=user_id,
        role=MemberRole.ADMIN,
    )
    session.add(membership)
    session.flush()
    return group


def create_test_expense(
    session,
    group_id: int,
    amount: str,
    creator_id: int,
    payer_id: int,
    description: str = "Test expense",
    status: str = "PENDING",
):
    """Create a test expense directly in the database."""
    from datetime import date

    from app.adapters.sqlalchemy.orm_models import ExpenseRow
    from app.domain.models import ExpenseStatus, SplitType

    expense = ExpenseRow(
        group_id=group_id,
        amount=amount,
        description=description,
        date=date.today(),
        creator_id=creator_id,
        payer_id=payer_id,
        currency="EUR",
        split_type=SplitType.EVEN,
        status=ExpenseStatus(status),
    )
    session.add(expense)
    session.flush()
    return expense
