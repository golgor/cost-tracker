# AGENTS.md - Cost Tracker

Instructions for AI coding agents working in this repository.

## Build / Lint / Test Commands

All commands use `mise` (task runner) and `uv` (package manager):

```bash
# Development
mise run dev              # Start dev server with reload
mise run dev:css          # Watch Tailwind CSS (run alongside dev)
mise run db               # Start PostgreSQL container
mise run migrate          # Run Alembic migrations

# Testing (requires PostgreSQL)
mise run test             # Run all tests
mise run test:unit        # Unit tests only
mise run test:integration # Integration tests only

# Single test file:
uv run pytest tests/domain/expenses_test.py -v

# Single test function:
uv run pytest tests/domain/expenses_test.py::test_create_expense -v

# Linting and Type Checking
mise run lint             # ruff check + ruff format --check + ty
mise run lint:fix         # Auto-fix ruff issues and format
mise run types            # Type check with pyright (fast)
mise run lint:docs        # Lint markdown in docs/
```

## Code Style Guidelines

### Formatting
- **Line length**: 120 characters
- **Quotes**: Double quotes for strings
- **Indentation**: 4 spaces
- **Python version**: 3.14+

### Imports
- Use `ruff` for import sorting (isort-compatible)
- First-party imports: `from app import ...`
- Standard library imports first, then third-party, then first-party
- Domain (`app/domain/`) must NOT import framework packages

### Naming Conventions
- **Domain ports**: `XxxPort` (e.g., `ExpensePort`)
- **Adapters**: `SqlAlchemyXxxAdapter` (e.g., `SqlAlchemyExpenseAdapter`)
- **ORM models**: `XxxRow` (e.g., `ExpenseRow`)
- **Domain models**: `XxxBase` (base), `XxxPublic` (public API)
- **Test files**: `{module}_test.py` (e.g., `expenses_test.py`)
- **Templates**: `snake_case.html`, HTMX partials prefixed `_`
- **Database tables**: plural snake_case (e.g., `expenses`, `users`)

### Architecture Rules
- **Hexagonal architecture**: Domain is pure Python (no FastAPI/SQLAlchemy imports)
- Only `dependencies.py` wires adapters to domain ports
- ORM models (`XxxRow`) never leave adapter boundary
- Use cases receive `UnitOfWork` as parameter (no global state)
- `queries/` is read-only — no writes permitted
- Never use `utils.py` or `helpers.py` — name by purpose (e.g., `splits.py`)

### Error Handling
- Never add `try/except` for domain errors in routes
- Use global exception handler (`DOMAIN_ERROR_MAP` in `main.py`)
- Define new `DomainError` subclasses as needed
- **Fail fast**: Use runtime assertions to validate assumptions instead of silently ignoring potential bugs
  - Example: `assert isinstance(value, str), "Expected string"` instead of casting or ignoring
  - Example: `assert form_data is not None, "form_data should exist when no errors"` for type narrowing
  - Prefer explicit validation over implicit coercion - if something shouldn't happen, make it fail loudly

### Type Safety
- Use type hints on all function signatures
- Return type `-> None` for procedures
- Use `from __future__ import annotations` where needed
- **Fail fast on type mismatches**: Add runtime assertions rather than ignoring type errors
  - Use `assert isinstance(x, ExpectedType)` to validate form inputs, API responses, etc.
  - Use `assert x is not None` for type narrowing when the type checker can't infer it
  - Never use `# type: ignore` to hide potential bugs - fix them explicitly or document with specific ignore codes

### Data Handling
- **Money**: Always use `Decimal`, never float
- **Money in JSON**: String representation (e.g., `"123.45"`)
- **Dates in JSON**: ISO 8601 with timezone
- **Database datetimes**: `DateTime(timezone=True)` — never naive
- **Audit logging**: Pass `actor_id` to adapter methods, don't call `uow.audit.log()` manually

### Testing
- All tests use PostgreSQL (no SQLite) — test DB auto-created with `_test` suffix
- Test pattern: `*_test.py`
- Use fixtures from `conftest.py` for UoW and sessions

### Test Fixture Transaction Management
**NEVER call `uow.session.commit()` in test fixtures.** Each test runs in a transaction that gets rolled back after the test. Committing early causes:
- Data leaks between tests
- Route transaction handling conflicts
- Inconsistent test state

**Correct pattern for test fixtures:**
```python
@pytest.fixture
def test_entity(uow: UnitOfWork):
    entity = EntityRow(name="test")
    uow.session.add(entity)
    uow.session.flush()  # Get ID without committing
    return entity
```

Use `flush()` to get auto-generated IDs without committing the transaction.

### CSRF Middleware & Form Data
**CRITICAL:** The CSRF middleware consumes the request body with `await request.form()` to validate the CSRF token. Once consumed, FastAPI's `Form()` dependency receives empty data because the body stream can only be read once.

**Solution:** Routes that use form data AND have CSRF protection must check for cached form data:

```python
# In routes that handle form POSTs with CSRF protection
cached_form = getattr(request.state, "_cached_form", None)
if cached_form:
    # Use cached form data (populated by CSRF middleware)
    expense_ids_str = cached_form.getlist("expense_ids")
    expense_ids = [int(eid) for eid in expense_ids_str if eid.isdigit()]
else:
    # Use FastAPI's Form dependency
    expense_ids: list[int] = Form(default=[])
```

**Always test POST routes with CSRF tokens** to catch this issue early.

### Templates (Jinja2)
- No complex business logic in templates
- Only boolean state checks for UI visibility
- Never compare values to literals or do numeric comparisons in templates
- Pass pre-computed boolean flags from view queries

## Common Tasks

```bash
# Add a dependency
uv add <package>

# Install from lockfile
uv sync --locked

# Run a single test
uv run pytest tests/domain/expenses_test.py::test_create_expense -v
```
