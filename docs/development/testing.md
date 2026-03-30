# Testing

Cost Tracker uses **pytest** with **PostgreSQL** for all tests. No SQLite — this eliminates
behavioral divergence around enum handling, constraint semantics, and transaction behavior.

## Running Tests

```bash
# All tests
mise run test

# Unit tests only (skips integration/)
mise run test:unit

# Integration tests only
mise run test:integration

# Single file
uv run pytest tests/domain/expenses_test.py -v

# Single test
uv run pytest tests/domain/expenses_test.py::test_create_expense_success -v

# Stop on first failure
uv run pytest -x
```

## Test Database

Tests auto-create a `_test` database derived from `DATABASE_URL`:

- `postgresql://user:pass@localhost/costtracker` becomes `costtracker_test`
- Override with `TEST_DATABASE_URL` env var (used in CI)
- Tables are created once per session, dropped after
- Each test runs in a **rolled-back transaction** — no data leaks between tests

## Test Organization

```text
tests/
├── conftest.py              # DB engine, session, UoW fixtures, test data helpers
├── architecture_test.py     # Enforces architectural rules
├── domain/                  # Use case tests
├── adapters/                # Adapter CRUD + contract tests
├── integration/             # Full-stack PostgreSQL tests
└── web/                     # Route handler tests with TestClient
```

Test files must end with `_test.py` (configured in `pyproject.toml`).

## Core Fixtures

### `db_engine` (session-scoped)

Creates a PostgreSQL engine pointing to the `_test` database. Creates all tables at session start,
drops them at session end.

### `db_session` (function-scoped)

Provides a transactional SQLAlchemy `Session`. Each test gets its own session with an open
transaction that is **rolled back** after the test — so tests are fully isolated.

### `uow` (function-scoped)

Wraps `db_session` in a `UnitOfWork` with all adapters pre-wired. This is the most commonly used
fixture.

### Test Data Helpers

`conftest.py` provides helper functions for creating test data:

```python
# Create users
user1 = create_test_user(session, "user1@test", "user1@test.com")
user2 = create_test_user(session, "user2@test", "user2@test.com")

# Create an expense
expense = create_test_expense(session, "50.00", payer_id=user1.id, creator_id=user1.id)
```

## Test Patterns

### Domain Unit Tests (with mocks)

For testing business logic in isolation, mock the `UnitOfWork`:

```python
def test_create_expense_validates_payer(mocker):
    uow = MagicMock()
    uow.users.get_by_id.return_value = None  # User doesn't exist

    with pytest.raises(UserNotFoundError):
        create_expense(uow=uow, payer_id=999, ...)
```

Use for: business rules, validation, error handling, decision logic.

### Domain Integration Tests (with database)

For testing use cases end-to-end through real adapters:

```python
def test_update_expense_changes_amount(uow, user1, user2):
    with uow:
        expense = create_expense(
            uow=uow,
            amount=Decimal("50.00"),
            description="Groceries",
            creator_id=user1.id,
            payer_id=user1.id,
        )

    with uow:
        update_expense(uow=uow, expense_id=expense.id, amount=Decimal("99.99"), actor_id=user1.id)

    with uow:
        updated = uow.expenses.get_by_id(expense.id)
        assert updated.amount == Decimal("99.99")
```

Use for: persistence, workflows, side effects like audit logging.

### Adapter Contract Tests

Verify that adapters correctly round-trip domain models without data loss:

```python
class TestUserAdapterContract:
    def test_save_and_retrieve_by_id(self, db_session):
        adapter = SqlAlchemyUserAdapter(db_session, SqlAlchemyAuditAdapter(db_session))
        user = adapter.save(oidc_sub="auth0|12345", email="test@example.com", ...)
        db_session.commit()

        retrieved = adapter.get_by_id(user.id)
        assert retrieved.oidc_sub == "auth0|12345"
        assert type(retrieved).__name__ == "UserPublic"  # Not UserRow
```

Use for: CRUD operations, boundary enforcement (`XxxRow` never escapes adapter).

### Web Route Tests

Test HTTP endpoints with `TestClient`:

```python
@pytest.fixture
def authenticated_client(user1, uow):
    app.dependency_overrides[get_uow] = lambda: uow
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set("cost_tracker_session", encode_session(user1.id))
    yield client
    app.dependency_overrides.clear()

def test_dashboard_shows_balance(authenticated_client, user1, uow):
    # Create test data
    uow.session.add(ExpenseRow(..., amount=Decimal("100.00")))
    uow.session.commit()

    response = authenticated_client.get("/")
    assert response.status_code == 200
    assert "owes you" in response.text
```

Authentication setup: encode a session token, set the cookie, and override the `get_uow`
dependency.

## Architecture Tests

`architecture_test.py` enforces structural rules automatically:

| Rule | What it checks |
| --- | --- |
| Domain import purity | No `fastapi`, `starlette`, `authlib`, `structlog` in `domain/` |
| Domain isolation | No imports from `app.adapters`, `app.web`, `app.auth` in `domain/` |
| Queries are read-only | No `.add()`, `.delete()`, `.commit()`, `.flush()` in `queries/` |
| No utils/helpers | No files named `utils.py` or `helpers.py` under `app/` |
| Template simplicity | No value comparisons or numeric logic in Jinja2 templates |

These tests use AST analysis and regex scanning — they run fast and catch violations early.

## Writing New Tests

### Checklist

1. Create `tests/{layer}/{feature}_test.py`
2. Use `uow` fixture for database tests, `MagicMock` for unit tests
3. Wrap database operations in `with uow:` context manager
4. Test both success and error paths
5. Verify side effects (audit logs, cascading updates)
6. Use descriptive test names: `test_delete_expense_removes_from_db`

### Transaction Pattern

Always use the context manager for database operations:

```python
with uow:
    # Operations here run in a transaction
    # Commits on normal exit
    # Rolls back on exception
    result = uow.expenses.save(...)
```
