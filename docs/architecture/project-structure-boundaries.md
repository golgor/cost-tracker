# Project Structure & Boundaries

## Complete Project Directory Structure

```text
cost-tracker/
├── pyproject.toml                          # Project metadata, pytest, ruff, ty config
├── uv.lock                                 # Locked dependencies for reproducible builds
├── mise.toml                               # Task runner + tool version management
├── alembic.ini                             # Alembic configuration
├── mkdocs.yml                              # MkDocs configuration
├── Dockerfile                              # Multi-stage: tailwind build → production image
├── docker-compose.yml                      # Local dev: PostgreSQL only (app runs via mise)
├── .env.example                            # Template for required env vars (committed)
├── .gitignore
├── .github/
│   └── workflows/
│       ├── code.yml                        # pytest + ruff + ty + schema drift (paths: app/, tests/)
│       ├── docs.yml                        # markdownlint + mkdocs build --strict (paths: docs/, mkdocs.yml)
│       └── docker.yml                      # Build + push to GHCR (paths: Dockerfile, app/)
├── alembic/
│   ├── __init__.py
│   ├── env.py                              # Imports app.adapters.sqlalchemy.orm_models.Base
│   ├── script.py.mako                      # Migration template
│   └── versions/                           # Auto-generated migration files
├── docs/
│   ├── index.md                            # Project overview
│   ├── architecture/
│   │   └── overview.md                     # Condensed arch overview + Mermaid diagram (links to full doc)
│   ├── development/
│   │   ├── setup.md                        # Local dev setup (mise, docker-compose, .env)
│   │   ├── conventions.md                  # Coding conventions (summary of implementation patterns)
│   │   └── adr.md                          # ADR index (links to architecture.md sections)
│   ├── deployment/
│   │   └── guide.md                        # Docker, GHCR, ArgoCD, k3s setup
│   └── user-guide/
│       ├── getting-started.md              # First-time: login → add expense
│       ├── expenses.md                     # Adding, editing, splitting, accepting/gifting
│       ├── settlements.md                  # Review, approve, confirm flow
│       ├── recurring.md                    # Creating definitions, auto-generation, editing
│       └── troubleshooting.md              # Common issues mapped to domain errors
├── app/
│   ├── __init__.py
│   ├── main.py                             # FastAPI app factory, exception handlers, middleware, /health/*
│   ├── settings.py                         # pydantic-settings Settings class
│   ├── logging.py                          # structlog configuration (processor chain, formatters)
│   ├── dependencies.py                     # Composition root: wires adapters → use cases
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py                       # SQLModel base classes: ExpenseBase, SettlementBase, RecurringDefinitionBase, UserBase + public read models + enums (SplitType, ExpenseStatus, RecurringFrequency)
│   │   ├── errors.py                       # DomainError hierarchy: ExpenseNotFound, InvalidSplit, etc.
│   │   ├── ports.py                        # Protocol interfaces: UserPort, ExpensePort, SettlementPort, RecurringDefinitionPort, UnitOfWorkPort
│   │   ├── balance.py                      # Balance calculation between partners
│   │   ├── recurring.py                    # Recurring expense generation logic
│   │   ├── value_objects.py                # Domain value objects
│   │   ├── splits/
│   │   │   ├── __init__.py
│   │   │   ├── strategies.py              # Split strategies: even/shares/percentage/exact
│   │   │   └── config.py                  # Split configuration
│   │   └── use_cases/
│   │       ├── __init__.py
│   │       ├── expenses.py                 # create, update, delete expense
│   │       ├── settlements.py              # review, confirm settlement
│   │       ├── recurring.py                # create/update definition, generate pending expenses
│   │       └── users.py                    # user provisioning and lookup
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── sqlalchemy/
│   │       ├── __init__.py
│   │       ├── orm_models.py               # Declarative Base + all XxxRow classes
│   │       ├── expense_adapter.py          # SqlAlchemyExpenseAdapter + _to_public()
│   │       ├── user_adapter.py             # SqlAlchemyUserAdapter + _to_public()
│   │       ├── settlement_adapter.py       # SqlAlchemySettlementAdapter + _to_public()
│   │       ├── recurring_adapter.py        # SqlAlchemyRecurringAdapter + _to_public()
│   │       ├── unit_of_work.py             # SqlAlchemyUnitOfWork (shared Session across all adapters)
│   │       └── queries/
│   │           ├── __init__.py
│   │           ├── admin_queries.py        # Admin dashboard queries
│   │           ├── api_queries.py          # API summary and expense queries
│   │           ├── dashboard_queries.py    # Balance summary, expense feed, recurring widget
│   │           ├── recurring_queries.py    # Recurring definition queries
│   │           ├── settlement_queries.py   # Settlement history, drill-down
│   │           └── mappings.py             # Shared query result mappings
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── oidc.py                         # Authentik OIDC flow via Authlib
│   │   ├── session.py                      # Signed cookie: encode/decode (user_id + issued_at)
│   │   └── middleware.py                   # Session validation, CSRF, HX-Redirect on expired session
│   ├── web/
│   │   ├── __init__.py
│   │   ├── router.py                       # Assembles all web routers (single include in main.py)
│   │   ├── dashboard.py                    # GET / → redirects to /expenses (per ADR-015)
│   │   ├── expenses/                       # /expenses — modular CRUD routes
│   │   │   ├── __init__.py
│   │   │   ├── crud.py                    # Create/update/delete
│   │   │   ├── list.py                    # List and search
│   │   │   ├── detail.py                  # Expense detail view
│   │   │   ├── notes.py                   # Expense notes CRUD
│   │   │   ├── preview.py                 # Split preview (HTMX)
│   │   │   └── _shared.py                 # Shared expense utilities
│   │   ├── settlements.py                  # /settlements — review/confirm flow, history
│   │   ├── recurring.py                    # /recurring — definition CRUD, manual generation
│   │   ├── admin.py                        # /admin — admin dashboard
│   │   ├── auth.py                         # /login, /callback, /logout — OIDC endpoints
│   │   ├── api_internal.py                 # /api/internal — server-side helpers (webhooks)
│   │   ├── view_models.py                  # View model preparation for templates
│   │   ├── filters.py                      # Jinja2 template filters
│   │   ├── form_parsing.py                 # Form data parsing utilities
│   │   ├── templates.py                    # Template engine configuration
│   │   └── forms/
│   │       ├── __init__.py
│   │       └── ...                         # Pydantic form models per feature
│   ├── api/
│   │   └── v1/                             # REST API for Glance dashboard integration
│   │       ├── __init__.py
│   │       ├── router.py                   # Assembles API routers, mounted at /api/v1
│   │       ├── auth.py                     # Bearer token authentication (GLANCE_API_KEY)
│   │       ├── expenses.py                 # GET /api/v1/expenses
│   │       └── schemas.py                  # Pydantic response models
│   ├── templates/
│   │   ├── base.html                       # Root layout: head, nav, content block, HTMX config
│   │   ├── _button.html                    # Reusable button component
│   │   ├── _card.html                      # Reusable card component
│   │   ├── _empty_state.html               # Contextual empty state partial
│   │   ├── _form_input.html                # Reusable form input component
│   │   ├── _nav_desktop.html               # Desktop navigation bar
│   │   ├── _nav_mobile.html                # Mobile navigation bar
│   │   ├── admin/
│   │   │   ├── users.html                 # Admin user list page
│   │   │   └── _user_row.html             # User row partial
│   │   ├── expenses/
│   │   │   ├── index.html                 # Expense list page
│   │   │   ├── _expense_feed.html         # Expense feed partial
│   │   │   ├── _expense_card.html         # Single expense card partial
│   │   │   ├── _expense_card_expanded.html # Expanded expense detail
│   │   │   ├── _expense_list_section.html # Expense list section
│   │   │   ├── _balance_bar.html          # Balance bar partial
│   │   │   ├── _filter_bar.html           # Filter/search bar partial
│   │   │   ├── _capture_form_mobile.html  # Mobile expense capture form
│   │   │   ├── _capture_form_desktop.html # Desktop expense capture form
│   │   │   ├── _edit_modal.html           # Edit expense modal
│   │   │   ├── _split_preview.html        # Split preview partial
│   │   │   ├── _expense_notes.html        # Notes section partial
│   │   │   ├── _expense_note_edit_form.html # Note edit form
│   │   │   ├── _bottom_sheet.html         # Mobile bottom sheet
│   │   │   ├── _fab_button.html           # Floating action button
│   │   │   └── _delete_confirmation_modal.html
│   │   ├── settlements/
│   │   │   ├── index.html                 # Settlement history page
│   │   │   ├── review.html                # Settlement review page (step 1)
│   │   │   ├── confirm.html               # Settlement confirm page (step 2)
│   │   │   ├── detail.html                # Settlement detail/drill-down
│   │   │   ├── success.html               # Settlement success page
│   │   │   └── _review_summary.html       # Review summary partial
│   │   ├── recurring/
│   │   │   ├── index.html                 # Recurring definitions list
│   │   │   ├── form.html                  # Create/edit definition form
│   │   │   ├── _definition_list.html      # Definition list partial
│   │   │   ├── _definition_card.html      # Definition card partial
│   │   │   ├── _summary_bar.html          # Summary bar partial
│   │   │   ├── _empty_state.html          # Empty state partial
│   │   │   └── _delete_modal.html         # Delete confirmation modal
│   │   └── auth/
│   │       ├── login.html                 # Login page (pre-OIDC redirect)
│   │       └── error.html                 # Auth error page
│   └── static/
│       ├── css/
│       │   └── output.css                  # Tailwind CSS build output
│       ├── js/
│       │   └── htmx.min.js                 # Vendored HTMX
│       └── favicon.ico
├── tests/
│   ├── __init__.py
│   ├── conftest.py                         # PostgreSQL engine (test DB), session factory, UoW factory
│   ├── architecture_test.py                # Domain purity, queries read-only, no utils.py/helpers.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── test_expenses.py                # Expense creation use cases
│   │   ├── update_expense_test.py          # Expense update use cases
│   │   ├── use_cases/
│   │   │   └── test_delete_expense.py     # Expense deletion use case
│   │   ├── settlements_test.py             # Settlement use cases
│   │   ├── balance_test.py                 # Balance calculation tests
│   │   ├── recurring_test.py               # Recurring generation domain logic
│   │   ├── recurring_use_cases_test.py     # Recurring use case tests
│   │   ├── splits_test.py                  # Split calculation, rounding edge cases
│   │   └── users_test.py                   # User use case tests
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── contract_test.py                # Round-trip mapping: XxxRow → _to_public()
│   │   ├── expense_search_query_test.py    # Expense search query tests
│   │   ├── recurring_adapter_test.py       # Recurring adapter tests
│   │   ├── settlement_adapter_test.py      # Settlement adapter tests
│   │   ├── test_dashboard_queries.py       # Dashboard query tests
│   │   └── unit_of_work_test.py            # UoW transaction tests
│   ├── api/
│   │   └── v1/
│   │       ├── glance_api_test.py          # Glance API integration tests
│   │       └── expenses_test.py            # API expense endpoint tests
│   ├── auth/
│   │   ├── csrf_test.py                    # CSRF protection tests
│   │   └── session_test.py                 # Session management tests
│   ├── integration/
│   │   ├── __init__.py
│   │   └── health_test.py                  # Health endpoint tests
│   └── web/
│       ├── __init__.py
│       ├── admin_ui_test.py                # Admin UI tests
│       ├── auth_routes_test.py             # Auth route tests
│       ├── dashboard_test.py               # Dashboard redirect tests
│       ├── exception_handler_test.py       # Error handling tests
│       ├── expense_detail_and_edit_test.py # Expense detail/edit tests
│       ├── expenses_list_test.py           # Expense list tests
│       ├── expenses_search_test.py         # Expense search tests
│       ├── recurring_form_test.py          # Recurring form tests
│       ├── recurring_test.py               # Recurring route tests
│       └── settlement_routes_test.py       # Settlement route tests
```

**Note:** Dependencies installed via `uv sync --locked`. Alembic imports from `app.adapters.sqlalchemy.orm_models.Base`
in `alembic/env.py`.

## Architectural Boundaries

**Domain Boundary (pure, no framework imports):**

- `app/domain/` imports only: `sqlmodel`, `pydantic`, `typing`, `decimal`, `datetime`, `enum`
- All external communication through `Protocol` interfaces in `ports.py`
- Use cases receive `UnitOfWork` as parameter — never instantiate adapters
- Enforced by `architecture_test.py` in CI

**Adapter Boundary (infrastructure implementations):**

- `app/adapters/sqlalchemy/` implements domain ports using SQLAlchemy
- ORM models (`XxxRow`) never leave adapter boundary — mapped to domain public models
  (e.g., `UserPublic`, `ExpensePublic`) via `_to_public()` before return
- ORM rows are created directly as `XxxRow(...)` since they inherit from domain base classes — no `_to_row()` needed
- Timestamp columns (`created_at`, `updated_at`) are server/SQLAlchemy-managed — adapters must not set them manually
- `queries/` package is a controlled read-only bypass for view queries — no writes permitted
- `unit_of_work.py` shares a single `Session` across all adapters
- Architectural test scans `queries/` directory for read-only enforcement

**Auth Boundary (infrastructure concern):**

- `app/auth/` handles OIDC flow, session cookies, CSRF, middleware
- Produces `user_id: int` for domain consumption — domain never sees cookies or tokens
- Session expiry on HTMX requests → `HX-Redirect` header

**Web Boundary (presentation layer):**

- `app/web/` handles HTTP routing, form parsing, template rendering
- `app/web/router.py` assembles all web routers — `main.py` includes only this single router
- `app/web/forms/` contains Pydantic models for form validation (distinct from domain SQLModel base classes)
- Calls use cases for mutations, `queries/` directly for read-only views
- Never contains business logic — thin handlers only

**API Boundary (external integration):**

- `app/api/v1/` provides read-only REST API for Glance dashboard integration
- Separate FastAPI sub-application mounted at `/api/v1`
- Bearer token authentication via `GLANCE_API_KEY` (distinct from web OIDC auth)
- Returns JSON responses using Pydantic response models

**Data Boundary:**

- All writes go through domain ports → adapters → `Session.commit()` via UoW
- Read-only views may use `queries/` directly (bypassing domain)
- Alembic migrations auto-generated from `orm_models.py`, always manually reviewed
- `SELECT FOR UPDATE` in settlement adapter for concurrent settlement protection

## Requirements to Structure Mapping

**Feature Mapping:**

| FR Category | Domain | Adapters | Routes | Templates |
| --- | --- | --- | --- | --- |
| Expense Management (FR1-FR8, FR46) | `use_cases/expenses.py`, `models.py`, `ports.py` | `expense_adapter.py`, `queries/dashboard_queries.py` | `web/expenses/` | `expenses/` |
| Split & Balance (FR9-FR12) | `splits/`, `balance.py` | `queries/dashboard_queries.py` | `web/expenses/` | `expenses/_balance_bar.html` |
| Settlement (FR13-FR22) | `use_cases/settlements.py`, `ports.py` | `settlement_adapter.py`, `queries/settlement_queries.py` | `web/settlements.py` | `settlements/` |
| Recurring Costs (FR23-FR29) | `use_cases/recurring.py`, `recurring.py`, `ports.py` | `recurring_adapter.py`, `queries/recurring_queries.py` | `web/recurring.py` | `recurring/` |
| User Management (FR39, FR42) | `use_cases/users.py`, `models.py` | `user_adapter.py` | `web/auth.py` | `auth/` |
| API Integration | — | `queries/api_queries.py` | `api/v1/` | — (JSON only) |

**Cross-Cutting Concerns Mapping:**

| Concern | Location |
| --- | --- |
| Authentication (OIDC) | `app/auth/oidc.py`, `app/auth/session.py` |
| Session + CSRF middleware | `app/auth/middleware.py` |
| Global error handling | `app/main.py` (exception handlers + `DOMAIN_ERROR_MAP`) |
| Logging configuration | `app/logging.py` (structlog setup, called from `main.py`) |
| App configuration | `app/settings.py` (pydantic-settings `Settings` class) |
| Dependency wiring | `app/dependencies.py` |
| Health checks | `app/main.py` (`/health/live` + `/health/ready` endpoints) |
| Database migrations | `alembic/` + `app/adapters/sqlalchemy/orm_models.py` |

## Integration Points

**Internal Communication:**

- Routes → Use cases: direct function calls via dependency injection
- Routes → View queries: direct import from `queries/` package
- Use cases → Adapters: through `UnitOfWork` port (no direct adapter access)
- Adapters → ORM: SQLAlchemy `Session` (shared within UoW)

**External Integrations:**

- Authentik (OIDC): `app/auth/oidc.py` via Authlib
- PostgreSQL: `app/adapters/sqlalchemy/` via SQLAlchemy engine
- Glance Dashboard: `app/api/v1/` via REST API with Bearer token
- GHCR: `.github/workflows/docker.yml` (build + push)
- ArgoCD: watches GHCR for new images (external to repo)

**Data Flow (write path with UoW context manager):**

```text
Browser → HTMX POST → web/expenses/crud.py
  → with uow: [
      use_cases/expenses.py → UnitOfWork
        → ExpensePort.save(expense) → SqlAlchemyExpenseAdapter → Session
    ] → UnitOfWork.__exit__() → Session.commit() → PostgreSQL
  → Jinja2 template (after context close) → HTML fragment
```

**Data Flow (read path — view query with UoW context manager):**

```text
Browser → HTMX GET → web/expenses/list.py
  → with uow: [
      queries/dashboard_queries.py → Session.execute(SELECT ...) → PostgreSQL
        → view data
    ] → UnitOfWork.__exit__() → Session.close()
  → Jinja2 template (after context close) → HTML fragment
```

**Settlement Flow (stateless review + atomic creation):**

```text
Browser → GET /settlements/review → web/settlements.py
  → with uow: [
      queries/settlement_queries.py → list_unsettled_expenses()
    ] → Session.close()
  → templates/settlements/review.html (checkbox form)

Browser → POST /settlements/confirm → web/settlements.py
  → Parse expense_ids from form
  → with uow: [
      uow.expenses.get_for_settlement(expense_ids) → validate all unsettled
      Calculate totals, splits, transfer direction
    ] → Session.close()
  → templates/settlements/confirm.html (summary + confirm form)

Browser → POST /settlements → web/settlements.py
  → Parse expense_ids + confirm data
  → with uow: [
      use_cases/settlements.confirm_settlement(uow, expense_ids)
        → Validate expenses still available (SELECT FOR UPDATE)
        → uow.settlements.save(settlement, expense_ids, transactions)
    ] → UnitOfWork.__exit__() → Session.commit()
  → Redirect to /settlements/{id}
```

**Settlement State Machine:**

```text
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│   PENDING   │────▶│   REVIEWING  │────▶│ SETTLED  │
│ (expenses)  │     │ (form state) │     │ (locked) │
└─────────────┘     └──────────────┘     └──────────┘
       │                                            │
       │ settlement_id assigned                     │ Soft immutability:
       │ (by adapter on link)                       │ - UI disables edits
       └────────────────────────────────────────────┘ - Use case raises error
```

**Key Implementation Notes:**

- **Concurrency protection**: `SELECT FOR UPDATE` on expenses during settlement creation
- **Idempotency**: Unique constraint on `reference` prevents duplicate monthly settlements
- **Validation**: Confirm page re-validates that all selected expenses are still unsettled (race condition protection)

**Session Lifecycle (UoW Context Manager):**

1. Route handler receives `UnitOfWork` via dependency injection
2. `with uow:` enters context → `UnitOfWork.__enter__()` called
3. All reads/writes occur via `uow.adapters.*` or `queries.*(uow.session)`
4. Context exit triggers `UnitOfWork.__exit__()`:
   - If no exception: `session.commit()` → changes persisted
   - If exception raised: `session.rollback()` → changes discarded
   - Always: `session.close()` → connection returned to pool
5. Template rendering occurs **after** step 4 — session is closed, no lazy-loading possible

## Documentation Structure

**Audience conventions:**

- `docs/development/` — developers (assumes Python + mise knowledge)
- `docs/user-guide/` — end users (assumes browser-only, no technical knowledge)
- `docs/operations/` — ops/self-hosters (assumes Docker + k8s, not necessarily Python)
- `docs/architecture/` — contributors (condensed overview with Mermaid diagrams, links to full architecture.md)

**API documentation:** Swagger UI at `/api/v1/docs` is the API reference (auto-generated by FastAPI). No separate
`docs/api/` section. API uses Bearer token authentication.

**Documentation CI:** `docs.yml` workflow runs `mkdocs build --strict` to catch broken internal links, in addition to
markdownlint.

## Development Workflow Integration

**Local Development (`mise` tasks):**

- `mise run dev`: starts `uvicorn` with reload + `tailwindcss --watch` (requires `uv sync --locked` first)
- `mise run test`: runs `pytest` (all tests use PostgreSQL with `_test` database suffix)
- `mise run lint`: runs `ruff check` + `ruff format --check` + `ty`
- `mise run migrate`: runs `alembic upgrade head`
- `mise run db`: starts PostgreSQL via `docker-compose up -d`
- Dependencies managed via `uv`: use `uv add <package>` to add, `uv remove <package>` to remove, `uv sync --locked` to
  install

**Build Process:**

- `Dockerfile` multi-stage: (1) Tailwind CSS build via Tailwind CLI, (2) production image with `uv` and locked
  dependencies
- Uses `ghcr.io/astral-sh/uv:python3.14-bookworm-slim` as builder base
- Builder stage requires `apt-get install curl ca-certificates` — slim images don't ship with `curl`, which is needed to
  download the Tailwind CLI binary
- Dependencies installed with `uv sync --locked` for reproducible builds
- No Node.js in production image — Tailwind CLI runs at build time only
- Single image contains app + static assets + compiled CSS

**Deployment:**

- Image pushed to GHCR by `docker.yml` workflow
- ArgoCD watches for new image tags → deploys to k3s
- PostgreSQL on separate Proxmox VM (connection string via k8s Secret)
- `.env.example` documents all required env vars for any deployment target
