# Implementation Patterns & Consistency Rules

## Pattern Categories Defined

**Critical Conflict Points Identified:**
15 areas where AI agents could make different choices, organized across naming, structure, format, communication, and
process patterns.

## Naming Patterns

**Database Naming Conventions:**

- Table names: `snake_case`, **plural** (e.g., `expenses`, `settlements`, `recurring_definitions`, `audit_logs`)
- Column names: `snake_case` (e.g., `group_id`, `created_at`, `settlement_id`)
- Foreign key columns: `{referenced_table_singular}_id` (e.g., `expense_id`, `user_id`)
- Indexes: `ix_{table}_{columns}` (e.g., `ix_expenses_group_id`, `ix_audit_logs_entity_type_entity_id`)
- Unique constraints: `uq_{table}_{columns}` (e.g., `uq_recurring_generations_definition_id_billing_period`)

**API Naming Conventions:**

- REST endpoints: **plural** nouns (e.g., `/expenses`, `/settlements`, `/groups`)
- URL path segments: `snake_case` (e.g., `/recurring_definitions`)
- Query parameters: `snake_case` (e.g., `?group_id=1&page_size=20`)
- HTMX endpoints share page paths, distinguished by `HX-Request` header

**Code Naming Conventions:**

- Files: `snake_case.py` (e.g., `expense_adapter.py`, `unit_of_work.py`)
- Classes: `PascalCase` (e.g., `SqlAlchemyExpenseAdapter`, `ExpenseRow`)
- Functions/methods: `snake_case` (e.g., `get_unsettled`, `mark_settled`)
- Variables: `snake_case` (e.g., `expense_ids`, `billing_period`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DOMAIN_ERROR_MAP`, `LOG_FORMAT`)
- Domain ports: `XxxPort` (e.g., `ExpensePort`, `SettlementPort`)
- SQLAlchemy adapters: `SqlAlchemyXxxAdapter` (e.g., `SqlAlchemyExpenseAdapter`)
- ORM models: `XxxRow(DomainBase, table=True)` inheriting from domain (e.g., `ExpenseRow`, `SettlementRow`)
- Domain base models: `SQLModel` without `table=True` (e.g., `ExpenseBase`, `SettlementBase`)
- Domain DTOs: `SQLModel` for input/output schemas (e.g., `ExpenseCreate`, `ExpensePublic`)
- Test files: `{module}_test.py` (e.g., `expenses_test.py`, `architecture_test.py`)
- Jinja2 templates: `snake_case.html`, HTMX partials prefixed with `_` (e.g., `_expense_row.html`)

## Structure Patterns

**Project Organization:**

- Tests co-located by architectural layer: `tests/domain/`, `tests/adapters/`, `tests/web/`, `tests/integration/`
- Test file naming: `{module}_test.py` suffix convention
- Requires `python_files = ["*_test.py"]` in `pyproject.toml` `[tool.pytest.ini_options]`
- Templates nested by domain area: `templates/expenses/`, `templates/settlements/`
- HTMX partials: `_` prefix within domain template folder (e.g., `templates/expenses/_row.html`)
- Static assets: vendored in `static/` (no CDN, no npm)

**Conftest Hierarchy:**

```text
tests/
  conftest.py               # Shared fixtures: PostgreSQL engine (test DB), session factory, UoW factory
  architecture_test.py      # Domain purity + queries.py enforcement
  domain/
    expenses_test.py
    settlements_test.py
    splits_test.py
  adapters/
    expense_adapter_test.py
    contract_test.py         # Round-trip mapping verification
  integration/
    conftest.py              # PostgreSQL fixtures (separate engine, CI-only)
    settlement_concurrency_test.py
  web/
    conftest.py              # TestClient + template rendering fixtures
    expense_routes_test.py
```

- Root `conftest.py`: PostgreSQL engine with `_test` database suffix (auto-derived from `DATABASE_URL`),
  `Session` factory, `UnitOfWork` factory. Creates test DB if needed. Used by all tests
- All tests use PostgreSQL: unit tests use `costtracker_test`, integration tests also use `costtracker_test`
- `web/conftest.py`: FastAPI `TestClient`, template assertion helpers

## Format Patterns

**API Response Formats (for future `/api/v1/`):**

- Success: direct resource or list — `{"id": 1, "description": "..."}` or `[{...}, {...}]`
- Error: `{"error": "<error_code>", "detail": "<human_message>"}`
- Error codes: `snake_case` identifiers (e.g., `expense_not_found`, `invalid_split`, `concurrent_settlement`)
- HTTP status codes follow standard semantics: 404 (not found), 409 (conflict), 422 (validation)

**HTMX Response Formats:**

- Success: HTML fragment for `hx-swap` target
- Error: `_error.html` partial rendered with appropriate status code
- Redirect: `HX-Redirect` header (e.g., expired session → Authentik login)

**Global Exception Handler Pattern:**

```python
DOMAIN_ERROR_MAP: dict[type[DomainError], tuple[int, str]] = {
    ExpenseNotFound: (404, "expense_not_found"),
    ExpenseSettled: (409, "expense_already_settled"),
    InvalidSplit: (422, "invalid_split"),
    ConcurrentSettlement: (409, "concurrent_settlement"),
    PermissionDenied: (403, "permission_denied"),
}

@app.exception_handler(DomainError)
def handle_domain_error(request: Request, exc: DomainError):
    status, code = DOMAIN_ERROR_MAP.get(type(exc), (500, "internal_error"))
    if is_htmx_request(request):
        return templates.TemplateResponse(
            "_error.html", {"message": str(exc)}, status_code=status
        )
    return JSONResponse(status_code=status, content={"error": code, "detail": str(exc)})
```

- **No per-route try/except blocks** — all domain errors handled by the global handler
- Route handlers are clean: validate input, call use case, render response
- New domain errors only require adding an entry to `DOMAIN_ERROR_MAP`

**Data Exchange Formats:**

- JSON field naming: `snake_case` (matches Python and database)
- Dates in JSON: ISO 8601 strings (e.g., `"2026-03-15"`, `"2026-03-15T14:30:00Z"`)
- Money: string representation of `Decimal` in JSON (e.g., `"123.45"`) — never float
- Null handling: explicit `null` in JSON, `None` in Python — never empty string as null substitute
- Booleans: `true`/`false` (JSON standard)

**Timestamp Patterns:**

- All datetime columns use `TIMESTAMPTZ` (PostgreSQL `TIMESTAMP WITH TIME ZONE`) — never naive `TIMESTAMP`
- ORM fields declare `sa_type=DateTime(timezone=True)` for timezone-aware storage and retrieval
- Timestamp defaults are server/SQLAlchemy-managed, not set in Python application code:
  - `created_at`: `server_default=func.now()` — PostgreSQL generates on INSERT, immutable after creation
  - `updated_at`: `server_default=func.now()` + `onupdate=func.now()` — SQLAlchemy auto-injects on every UPDATE
  - `joined_at`, `occurred_at`: `server_default=func.now()` — PostgreSQL generates on INSERT
- Adapters must never manually assign `row.created_at` or `row.updated_at`
- Dates in JSON: ISO 8601 strings with timezone (e.g., `"2026-03-15T14:30:00+00:00"`)

**Route Handler Pattern (clean, no try/except):**

```python
@router.post("/expenses")
def create_expense(
    form: ExpenseForm = Depends(),
    uow: UnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_user),
):
    expense = domain_create_expense(
        uow=uow, user_id=current_user.id,
        description=form.description, amount=form.amount,
    )
    return templates.TemplateResponse("expenses/_row.html", {"expense": expense})
```

## Communication Patterns

**Logging Patterns:**

- Library: `structlog` with bound loggers
- Format: JSON in all environments (`LOG_FORMAT` env var for override)
- Domain layer does NOT log — raises errors or uses `AuditPort`
- Adapters log: DB query timings, connection events
- Middleware logs: request/response lifecycle, authentication events
- Log levels: `debug` (development detail), `info` (business events), `warning` (recoverable issues), `error` (failures
  requiring attention)
- Bound context: always include `request_id`, `user_id` where available

**Audit Trail Patterns:**

- Adapters auto-audit in mutating methods (`save()`, `update()`, `add_member()`) — use cases
  don't call audit manually
- Adapters receive the audit adapter via constructor injection
- Mutating adapter methods accept `actor_id` as a keyword parameter; user adapter's `save()`
  self-audits with the user's own ID (OIDC self-provisioning)
- `compute_changes(row)` reads SQLAlchemy `inspect()` attribute history for updates — captures
  old→new for changed fields only
- `snapshot_new(row)` builds a changes dict for creates — old is always `null`
- Changes stored as a single `changes` JSON column:
  `{"field": {"old": ..., "new": ...}}`
- No audit row is created if nothing actually changed (update with identical values)
- Audit entries are atomic with data changes (same transaction via UoW)
- `AuditPort` still exists for direct use if needed, but adapters handle the common case
- Actions: `snake_case` verbs (e.g., `expense_created`, `expense_deleted`,
  `settlement_confirmed`)
- **New adapter checklist:** every new adapter with mutating methods must (1) receive
  `SqlAlchemyAuditAdapter` via constructor, (2) use `compute_changes()` for updates and
  `snapshot_new()` for creates from `app/adapters/sqlalchemy/changes.py`, (3) accept
  `actor_id` as a keyword parameter on all mutating methods, (4) include auto-audit tests

## Process Patterns

**Error Handling Patterns:**

- Domain errors: custom exception classes inheriting from `DomainError`
- Global exception handler maps domain errors to HTTP responses (see Format Patterns above)
- Route handlers never catch domain errors — they propagate to the global handler
- Infrastructure errors (DB connection, OIDC failures): logged by middleware, generic 500 to user
- Validation errors: Pydantic `RequestValidationError` handled by FastAPI's built-in handler (422)

**Loading State Patterns:**

- HTMX loading indicators: `hx-indicator` attribute pointing to spinner element
- Opacity fade: 150ms baseline transition on `htmx-request` class
- Double-submit prevention: `hx-disabled-elt="this"` on all mutation buttons
- Full-page loads: standard browser loading (no SPA shell)

**Dependency Injection Pattern:**

```python
# app/dependencies.py — composition root
def get_uow() -> UnitOfWork:
    session = SessionLocal()
    return SqlAlchemyUnitOfWork(session)

def get_user(request: Request) -> User:
    """Extract authenticated user from signed cookie."""
    ...
```

- `dependencies.py` is the only file that wires adapters to domain ports
- Use cases receive `UnitOfWork` as a parameter — no global state, no service locator
- Current user enters domain as `user_id: int` parameter, not framework-specific request context

## Enforcement Guidelines

**All AI Agents MUST:**

- Follow the `XxxPort` / `SqlAlchemyXxxAdapter` / `XxxRow` naming convention — no variations
- Use `{module}_test.py` suffix for all test files
- Never add `try/except` for domain errors in route handlers — use the global exception handler
- Never import framework packages in `domain/` — enforced by `architecture_test.py`
- Never use `utils.py` or `helpers.py` as file names — name by purpose (e.g., `splits.py`, `formatting.py`)
- Never write to DB in `queries.py` — enforced by architectural test
- Always use `Decimal` for money values — zero floats in the money path
- Never call `uow.audit.log()` manually in use cases — adapters auto-audit in mutating methods (see Audit Trail Patterns)
- Never manually assign `created_at` or `updated_at` in adapters — these are server/SQLAlchemy-managed
- Always use `DateTime(timezone=True)` for datetime columns — never naive timestamps

**Pattern Enforcement:**

- `architecture_test.py` validates: domain import purity, `queries.py` read-only, no `utils.py`/`helpers.py`
- `contract_test.py` validates: round-trip ORM mapping preserves all fields
- Code review checklist: naming conventions, no per-route error handling, audit logging presence
- CI runs all enforcement tests on every PR

## Pattern Examples

**Good Examples:**

```python
# Domain port — named for intent
class ExpensePort(Protocol):
    def get_unsettled(self, group_id: int) -> list[Expense]: ...

# Adapter — implements port, ORM internal
class SqlAlchemyExpenseAdapter:
    def get_unsettled(self, group_id: int) -> list[Expense]:
        rows = self._session.query(ExpenseRow).filter_by(
            group_id=group_id, settlement_id=None
        ).all()
        return [_to_public(row) for row in rows]

# Use case — pure function, receives UoW
def create_expense(uow: UnitOfWork, user_id: int, ...) -> Expense:
    expense = Expense(...)
    saved = uow.expenses.save(expense, actor_id=user_id)  # adapter auto-audits
    uow.commit()
    return saved

# Route — clean, no try/except
@router.post("/expenses")
def create_expense_route(form: ExpenseForm = Depends(), uow: UnitOfWork = Depends(get_uow), current_user: User = Depends(get_user)):
    expense = domain_create_expense(uow=uow, user_id=current_user.id, description=form.description, amount=form.amount)
    return templates.TemplateResponse("expenses/_row.html", {"expense": expense})
```

**Anti-Patterns:**

```python
# BAD: Generic file names
utils.py          # What utils? Name by purpose
helpers.py        # Same problem — be specific

# BAD: Per-route error handling
@router.post("/expenses")
def create_expense(...)
    try:
        expense = domain_create_expense(...)
    except ExpenseNotFound:
        return templates.TemplateResponse("_error.html", ...)

# BAD: Framework imports in domain
from pydantic import BaseModel  # NO — domain uses SQLModel (not raw Pydantic)
from sqlalchemy import Column      # NO — ORM stays in adapters

# BAD: Repository naming (use adapter pattern)
class ExpenseRepository: ...       # NO — use ExpensePort (domain) + SqlAlchemyExpenseAdapter (infra)

# BAD: Floats for money
amount: float = 19.99              # NO — use Decimal("19.99")

# BAD: Manual audit.log() in use case — adapters handle this automatically
def create_expense(uow, user_id, ...):
    saved = uow.expenses.save(expense, actor_id=user_id)
    uow.audit.log(...)             # NO — adapter already auto-audited in save()
    uow.commit()

# BAD: Manual timestamp assignment in adapters
row.updated_at = datetime.now(UTC)  # NO — onupdate=func.now() handles this
row.created_at = datetime.now(UTC)  # NO — server_default=func.now() handles this

# BAD: Python-side default factories for timestamps
created_at: datetime = Field(default_factory=_utc_now)  # NO — use server_default=func.now()
```
