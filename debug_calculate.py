"""Debug calculate total endpoint."""

import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("OIDC_ISSUER", "https://test.example.com")
os.environ.setdefault("OIDC_CLIENT_ID", "test-client")
os.environ.setdefault("OIDC_CLIENT_SECRET", "test-secret")
os.environ.setdefault("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback")
os.environ.setdefault("ENV", "dev")

from datetime import date
from decimal import Decimal

from starlette.testclient import TestClient

from app.adapters.sqlalchemy.orm_models import (
    ExpenseRow,
    GroupRow,
    MembershipRow,
    UserRow,
)
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.auth.session import encode_session
from app.dependencies import get_uow
from app.domain.models import ExpenseStatus, MemberRole, SplitType, UserRole
from app.main import app

from app.settings import settings
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel
from urllib.parse import urlparse

def get_test_database_url():
    db_url = str(settings.DATABASE_URL)
    parsed = urlparse(db_url)
    original_db = parsed.path.lstrip("/")
    test_db = f"{original_db}_test"
    test_url = (
        f"{parsed.scheme}://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/{test_db}"
    )
    return test_url

test_url = get_test_database_url()
engine = create_engine(test_url)
SQLModel.metadata.create_all(engine)

connection = engine.connect()
transaction = connection.begin()
session = Session(bind=connection)

uow = UnitOfWork(session=session)

# Setup test data
user1 = UserRow(
    oidc_sub="user1@test.com",
    email="user1@test.com",
    display_name="Alice",
    role=UserRole.USER,
)
uow.session.add(user1)
uow.session.flush()

user2 = UserRow(
    oidc_sub="user2@test.com",
    email="user2@test.com",
    display_name="Bob",
    role=UserRole.USER,
)
uow.session.add(user2)
uow.session.flush()

group = GroupRow(
    name="Test Household",
    singleton_guard=True,
    default_currency="EUR",
    default_split_type=SplitType.EVEN,
)
uow.session.add(group)
uow.session.flush()

from app.adapters.sqlalchemy.orm_models import MembershipRow, MemberRole
uow.session.add(MembershipRow(group_id=group.id, user_id=user1.id, role=MemberRole.ADMIN))
uow.session.add(MembershipRow(group_id=group.id, user_id=user2.id, role=MemberRole.USER))

expense1 = ExpenseRow(
    group_id=group.id,
    amount=Decimal("100.00"),
    description="Test expense 1",
    date=date.today(),
    creator_id=user1.id,
    payer_id=user1.id,
    currency="EUR",
    split_type=SplitType.EVEN,
    status=ExpenseStatus.PENDING,
)
uow.session.add(expense1)
uow.session.flush()

expense2 = ExpenseRow(
    group_id=group.id,
    amount=Decimal("50.00"),
    description="Test expense 2",
    date=date.today(),
    creator_id=user2.id,
    payer_id=user2.id,
    currency="EUR",
    split_type=SplitType.EVEN,
    status=ExpenseStatus.PENDING,
)
uow.session.add(expense2)
uow.session.flush()

print(f"Created expenses: {expense1.id}, {expense2.id}")

# Setup client
app.dependency_overrides[get_uow] = lambda: uow

client = TestClient(app, raise_server_exceptions=False)
session_token = encode_session(user1.id)
client.cookies.set("cost_tracker_session", session_token)

# Get CSRF token
get_response = client.get("/settlements/review")
csrf_token = get_response.cookies.get("csrf_token")
print(f"CSRF token: {csrf_token}")

# Test calculate-total endpoint (simulating HTMX request)
print("\n=== Testing calculate-total with one expense ===")
response = client.post(
    "/settlements/calculate-total",
    data={
        "expense_ids": str(expense1.id),
        "_csrf_token": csrf_token,
    },
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")

# Check if expense_count appears in response
if "1 expense" in response.text:
    print("✓ Expense count is 1")
else:
    print("✗ Expense count is NOT 1")

if "50.00" in response.text or "€50" in response.text or "100.00" in response.text or "€100" in response.text:
    print("✓ Amount appears in response")
else:
    print("✗ Amount does NOT appear in response")

# Cleanup
app.dependency_overrides.clear()
session.close()
if transaction.is_active:
    transaction.rollback()
connection.close()
engine.dispose()
