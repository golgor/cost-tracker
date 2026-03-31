# Lessons Learned

Patterns and corrections captured during development. Review at session start.
Promote recurring patterns that prove critical into architecture tests.

## Naming

- Follow `XxxPort` / `SqlAlchemyXxxAdapter` / `XxxRow` naming — no variations
- No `Repository` naming — use `Port` (domain) + `Adapter` (infra)
- Never use `utils.py` or `helpers.py` as file names — name by purpose (e.g., `splits.py`, `formatting.py`)

## Domain Purity

- Never import framework packages in `domain/` — enforced by `architecture_test.py`
- Never write to DB in `queries/` — enforced by architectural test

## Error Handling

- Never add `try/except` for domain errors in route handlers — use the global exception handler (`DOMAIN_ERROR_MAP` in `main.py`). Route handlers stay clean: validate input, call use case, render response. New errors only need a map entry.

## Templates

- Jinja2 templates contain no value comparisons or complex business logic — only boolean state checks for UI visibility (e.g., `{% if expense.is_settled %}`). Never compare values to literals (`user.role == "admin"`) or do numeric comparisons (`amount > 100`). Pass pre-computed boolean flags from view queries instead. Enforced by `test_templates_contain_no_complex_business_logic()` in `architecture_test.py`

## Data Handling

- Always use `Decimal` for money values — zero floats in the money path
- Money in JSON: string representation of `Decimal` (e.g., `"123.45"`) — never float
- Dates in JSON: ISO 8601 strings with timezone (e.g., `"2026-03-15T14:30:00+00:00"`)
- Always use `DateTime(timezone=True)` for datetime columns — never naive `TIMESTAMP`
- Never manually assign `created_at` or `updated_at` in adapters — server/SQLAlchemy-managed via `server_default=func.now()` and `onupdate=func.now()`

## Form Parameters

- Always use `Annotated[T, Form()]` — never `T = Form(...)` or manual `await request.form()`. Use `alias` when the HTML field name differs from the Python parameter name (e.g., `date_str: Annotated[str, Form(alias="date")]`).
- For `list` defaults, use `None` (not `[]`) to satisfy ruff B006, and initialize to `[]` in the function body.

```python
@router.post("/example")
async def example(
    name: Annotated[str, Form()],                              # required
    description: Annotated[str, Form()] = "",                   # optional with default
    date_str: Annotated[str, Form(alias="date")] = "",          # alias maps HTML field name
    items: Annotated[list[int] | None, Form()] = None,          # list type (None default)
):
```

## CSRF Middleware

- The CSRF middleware (`app/auth/middleware.py`) calls `await request.body()` before `await request.form()`. This is critical — Starlette's `_CachedRequest` only replays the body if `body()` was called first. Without it, `form()` consumes the stream and FastAPI's `Form()` injection gets empty data (422 errors). Do not remove the `await request.body()` call. Always test POST routes with CSRF tokens.

## Test Fixtures

- **NEVER call `uow.session.commit()` in test fixtures.** Each test runs in a transaction that gets rolled back. Committing causes data leaks between tests. Use `flush()` to get IDs without committing.

```python
@pytest.fixture
def test_entity(uow: UnitOfWork):
    entity = EntityRow(name="test")
    uow.session.add(entity)
    uow.session.flush()  # Get ID without committing
    return entity
```

## Type Safety

- Type hints on all function signatures, `-> None` for procedures
- Fail fast: `assert isinstance(value, str)` over silent casting
- `assert x is not None` for type narrowing when the type checker can't infer it
- Never use `# type: ignore` to hide potential bugs — fix explicitly or use specific ignore codes
- Audit logging: pass `actor_id` to adapter methods, don't call `uow.audit.log()` manually

<!-- New lessons go below this line. Format: ## Category heading, then bullet points. -->

## Commands

- Use `mise run lint:fix` (auto-fix) then `mise run lint` (verify) — never raw `ruff` commands
- Use `mise run types` for type-checking — never raw `ty` commands
- Use `mise run test` or `uv run pytest tests/path/file.py -v` for running tests — never `python -c` for verification

## API Sub-Application

- `api_v1` is a separate FastAPI sub-app mounted at `/api/v1`. It does NOT inherit exception handlers from the main `app`. Add a JSON-only domain error handler directly to `api_v1` in `router.py`.
- When adding new domain errors that need 404/40x treatment in both web and API routes, add them to `DOMAIN_ERROR_MAP` in `main.py` AND to the equivalent handler in `api_v1`.
