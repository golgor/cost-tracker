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

## UI Consistency

- Keep Flowbite as the behavior layer, but enforce one visual system via shared classes in `app/static/src/input.css`.
- Use shared page wrappers consistently:
  - `ct-page-tight` for form-focused pages
  - `ct-page` for standard pages
  - `ct-page-wide` for dashboard/list-heavy pages
- Use shared action classes for consistency across templates:
  - `ct-btn-primary` for primary actions
  - `ct-btn-secondary` for secondary actions
- Use `ct-input` as default input/select style unless there is an explicit exception.
- Keep navbar-to-content spacing consistent by relying on `base.html` main padding, not per-page ad hoc top spacing.
- Preserve stable button text alignment when using loading indicators (spinner must not shift label text).
- For recurring filters (tabs/chips), always render explicit selected-state styling so active filter is visible.

## UI Change Safety

- For cross-page visual consistency work, change one layer at a time: shared tokens/classes first, then one route at a time (`/expenses`, `/trips`, `/recurring`, `/settlements`). Avoid broad multi-page rewrites in one pass.
- After each UI pass, verify all primary routes before continuing to prevent regressions from accumulating.
- Keep layout-shell changes (page wrappers/spacing) separate from component-style changes (buttons/inputs/cards) to limit blast radius.

## Tailwind Build Discipline

- After adding new component classes or theme tokens in `app/static/src/input.css`, rebuild `app/static/css/output.css` before evaluating UI changes.
- If Tailwind compilation fails with unknown utilities (for example `hover:bg-primary-700`), add missing theme tokens first, then rebuild.

## Template Merge Hygiene

- After conflict resolution in templates, always scan for broken Jinja expressions and malformed comparisons (for example `member.id == current_user_id`).
- Immediately run at least one route render test for touched templates to catch syntax errors early.

## Interaction Predictability

- Prefer deterministic custom components over Flowbite defaults when strict interaction contracts are required (date range picker commit behavior is a known example).
- For HTMX-swapped filter UIs, active state must be encoded in server-rendered markup so users can always see current selection.

## UI Text and Tests

- When changing CTA copy for UX reasons, preserve existing test hooks unless tests are intentionally updated (for example keep legacy text in `sr-only` labels).
- Run `mise run test:unit` after substantial template/UI changes, not only lint checks.
