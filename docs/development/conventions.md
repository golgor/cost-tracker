# Conventions

Coding conventions, naming rules, and patterns for Cost Tracker. This document extracts the
key rules in human-readable form. The authoritative and complete reference is
[CLAUDE.md](https://github.com/golgor/cost-tracker/blob/main/CLAUDE.md) at the project root.

## Architecture

Cost Tracker follows **hexagonal architecture** (ports & adapters). The domain layer is pure
Python with no framework imports.

### Layer Boundaries

- `domain/` imports only: `sqlmodel`, `pydantic`, `typing`, `decimal`, `datetime`, `enum`
- ORM models (`XxxRow`) never leave the adapter boundary — mapped to public domain models via
  `_to_public()`
- Use cases receive `UnitOfWork` as a parameter — no global state, no service locator
- `dependencies.py` is the **only** file that wires adapters to domain ports
- Routes call use cases for mutations, `queries/` directly for read-only views
- `queries/` is strictly read-only — no writes permitted

These boundaries are enforced by `architecture_test.py`.

## Naming

### Code

| Concept | Convention | Example |
| --- | --- | --- |
| Domain port | `XxxPort` | `ExpensePort` |
| Adapter | `SqlAlchemyXxxAdapter` | `SqlAlchemyExpenseAdapter` |
| ORM model | `XxxRow` | `ExpenseRow` |
| Domain base model | `XxxBase(SQLModel)` | `ExpenseBase` |
| Domain public model | `XxxPublic(XxxBase)` | `ExpensePublic` |
| Test file | `{module}_test.py` | `expenses_test.py` |
| Template | `snake_case.html` | `expense_list.html` |
| HTMX partial | `_partial.html` | `_row.html` |

### Database

| Concept | Convention | Example |
| --- | --- | --- |
| Table | `snake_case`, **plural** | `expenses`, `recurring_definitions` |
| Foreign key | `{referenced_table_singular}_id` | `expense_id` |
| Index | `ix_{table}_{columns}` | `ix_expenses_date` |
| Unique constraint | `uq_{table}_{columns}` | `uq_users_email` |

### API

- REST endpoints use **plural** nouns with `snake_case` paths
- HTMX endpoints share page paths, distinguished by `HX-Request` header
- API prefix: `/api/v1/` (deferred post-MVP)

## Mandatory Rules

These rules are non-negotiable. Violations will be caught by tests or code review.

### Error Handling

- **Never** add `try/except` for domain errors in route handlers — use the global exception
  handler (`DOMAIN_ERROR_MAP` in `main.py`)
- New domain errors only need an entry in the map

### File Naming

- **Never** use `utils.py` or `helpers.py` — name files by purpose (e.g., `splits.py`,
  `formatting.py`)
- No `Repository` naming — use `Port` (domain) + `Adapter` (infra)

### Templates

- Templates contain **no value comparisons** or complex business logic
- Only boolean state checks for UI visibility: `{% if expense.is_settled %}`
- Never compare values to literals or do numeric comparisons
- Pass pre-computed boolean flags from view queries instead

### Money and Data

- Always use `Decimal` for money — zero floats in the money path
- Money in JSON: string representation (`"123.45"`, never float)
- Dates in JSON: ISO 8601 with timezone (`"2026-03-15T14:30:00+00:00"`)
- Always use `DateTime(timezone=True)` for datetime columns

### Adapters and Audit

- Every adapter with mutating methods must implement auto-auditing
- Receive `SqlAlchemyAuditAdapter` via constructor
- Use `compute_changes()` for updates and `snapshot_new()` for creates
- Never manually assign `created_at` or `updated_at` — server-managed via `func.now()`

### Forms

- Always use `Annotated[T, Form()]` for form parameters
- Use `alias` when the HTML field name differs from the Python parameter name

## Dev Commands

| Command | Purpose |
| --- | --- |
| `mise run dev` | Start dev server (uvicorn + Tailwind watch) |
| `mise run test` | Run all tests (requires PostgreSQL) |
| `mise run lint` | Ruff check + format check + type check |
| `mise run lint:fix` | Auto-fix lint/format issues |
| `mise run lint:docs` | Markdownlint on docs |
| `mise run migrate` | Run Alembic migrations |
| `mise run db` | Start PostgreSQL via Docker Compose |

## Package Management

- Use **uv** (Astral) — never use pip directly
- `uv add <pkg>` to add dependencies
- `uv sync --locked` to install from lockfile
- `uv.lock` is committed for reproducible builds
