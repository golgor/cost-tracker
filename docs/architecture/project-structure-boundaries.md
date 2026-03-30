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
│   ├── main.py                             # FastAPI app factory, exception handlers, middleware, /health
│   ├── settings.py                         # pydantic-settings Settings class
│   ├── logging.py                          # structlog configuration (processor chain, formatters)
│   ├── dependencies.py                     # Composition root: wires adapters → use cases
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── models.py                       # SQLModel base classes: ExpenseBase, SettlementBase, RecurringDefinitionBase, AuditEntryBase, UserBase + public read models
│   │   ├── errors.py                       # DomainError hierarchy: ExpenseNotFound, InvalidSplit, etc.
│   │   ├── ports.py                        # Protocol interfaces: ExpensePort, SettlementPort, RecurringPort, AuditPort, UnitOfWork
│   │   ├── splits.py                       # Pure math: even/shares/percentage/amount split, deterministic rounding
│   │   └── use_cases/
│   │       ├── __init__.py
│   │       ├── expenses.py                 # create, update, delete, accept, gift expense
│   │       ├── settlements.py              # review, confirm settlement
│   │       └── recurring.py                # create/update definition, generate pending expenses
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── sqlalchemy/
│   │       ├── __init__.py
│   │       ├── orm_models.py               # Declarative Base + all XxxRow classes
│   │       ├── expense_adapter.py          # SqlAlchemyExpenseAdapter + _to_public()
│   │       ├── settlement_adapter.py       # SqlAlchemySettlementAdapter + _to_public()
│   │       ├── recurring_adapter.py        # SqlAlchemyRecurringAdapter + _to_public()
│   │       ├── audit_adapter.py            # SqlAlchemyAuditAdapter + _to_public()
│   │       ├── unit_of_work.py             # SqlAlchemyUnitOfWork (shared Session across all adapters)
│   │       └── queries/
│   │           ├── __init__.py
│   │           ├── dashboard_queries.py    # Balance summary, expense feed, recurring widget
│   │           ├── expense_queries.py      # Expense search, filtered lists
│   │           ├── settlement_queries.py   # Settlement history, drill-down
│   │           └── audit_queries.py        # Audit trail views
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── oidc.py                         # Authentik OIDC flow via Authlib
│   │   ├── session.py                      # Signed cookie: encode/decode (user_id + issued_at)
│   │   └── middleware.py                   # Session validation, CSRF, HX-Redirect on expired session
│   ├── web/
│   │   ├── __init__.py
│   │   ├── router.py                       # Assembles all web routers (single include in main.py)
│   │   ├── dashboard.py                    # GET / — balance summary, expense feed, recurring widget
│   │   ├── expenses.py                     # /expenses — CRUD routes, HTMX partials
│   │   ├── settlements.py                  # /settlements — review/confirm flow, history
│   │   ├── recurring.py                    # /recurring — definition CRUD, manual generation
│   │   ├── auth.py                         # /login, /callback, /logout — OIDC endpoints
│   │   └── forms/
│   │       ├── __init__.py
│   │       ├── expenses.py                 # ExpenseForm, SplitForm (Pydantic)
│   │       ├── settlements.py              # SettlementConfirmForm (Pydantic)
│   │       └── recurring.py                # RecurringDefinitionForm (Pydantic)
│   ├── api/
│   │   └── v1/                             # Deferred post-MVP
│   │       ├── __init__.py
│   │       └── router.py                   # Future: assembles all API routers
│   ├── templates/
│   │   ├── base.html                       # Root layout: head, nav, content block, global error handler, HTMX config
│   │   ├── shared/
│   │   │   ├── _nav.html                   # Navigation bar
│   │   │   ├── _footer.html                # Footer
│   │   │   ├── _error.html                 # Global error partial (used by exception handler)
│   │   │   ├── _loading.html               # Loading spinner partial
│   │   │   ├── _empty_state.html           # Contextual empty state partial
│   │   │   └── _pagination.html            # Pagination controls
│   │   ├── dashboard/
│   │   │   ├── index.html                  # Dashboard page (FR30-FR38)
│   │   │   ├── _balance_summary.html       # Balance widget partial
│   │   │   ├── _expense_feed.html          # Expense feed with tabs partial
│   │   │   └── _recurring_widget.html      # Recurring cost summary partial
│   │   ├── expenses/
│   │   │   ├── index.html                  # Expense list page
│   │   │   ├── create.html                 # Create expense form page
│   │   │   ├── detail.html                 # Expense detail page
│   │   │   ├── _row.html                   # Single expense row partial
│   │   │   ├── _form.html                  # Expense form partial (create/edit)
│   │   │   ├── _splits.html                # Split configuration partial
│   │   │   └── _notes.html                 # Per-expense notes partial
│   │   ├── settlements/
│   │   │   ├── index.html                  # Settlement history page
│   │   │   ├── review.html                 # Settlement review page (step 1)
│   │   │   ├── confirm.html                # Settlement confirm page (step 2)
│   │   │   ├── detail.html                 # Settlement detail/drill-down
│   │   │   ├── _row.html                   # Settlement history row partial
│   │   │   └── _review_summary.html        # Review summary partial
│   │   ├── recurring/
│   │   │   ├── index.html                  # Recurring definitions list
│   │   │   ├── create.html                 # Create definition form
│   │   │   ├── detail.html                 # Definition detail
│   │   │   ├── _row.html                   # Definition row partial
│   │   │   └── _form.html                  # Definition form partial
│   │   └── auth/
│   │       └── login.html                  # Login page (pre-OIDC redirect)
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
│   │   ├── expenses_test.py                # Expense use cases via real adapters + PostgreSQL
│   │   ├── settlements_test.py             # Settlement use cases via real adapters + PostgreSQL
│   │   ├── recurring_test.py               # Recurring generation use cases
│   │   └── splits_test.py                  # Pure math: split calculation, rounding edge cases
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── expense_adapter_test.py         # Adapter CRUD operations
│   │   └── contract_test.py                # Round-trip mapping: XxxRow → _to_public() preserves all fields
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── conftest.py                     # PostgreSQL fixtures (TEST_DATABASE_URL)
│   │   └── settlement_concurrency_test.py  # SELECT FOR UPDATE, idempotency constraints
│   └── web/
│       ├── __init__.py
│       ├── conftest.py                     # TestClient, template assertion helpers
│       └── expense_routes_test.py          # Full request cycle through routes
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

**Data Boundary:**

- All writes go through domain ports → adapters → `Session.commit()` via UoW
- Read-only views may use `queries/` directly (bypassing domain)
- Alembic migrations auto-generated from `orm_models.py`, always manually reviewed
- `SELECT FOR UPDATE` in settlement adapter for concurrent settlement protection

## Requirements to Structure Mapping

**Feature Mapping:**

| FR Category | Domain | Adapters | Routes | Templates |
| --- | --- | --- | --- | --- |
| Expense Management (FR1-FR8, FR46) | `use_cases/expenses.py`, `models.py`, `ports.py` | `expense_adapter.py`, `queries/expense_queries.py` | `web/expenses.py` | `expenses/` |
| Split & Balance (FR9-FR12) | `splits.py` | `queries/dashboard_queries.py` | `web/dashboard.py` | `dashboard/_balance_summary.html` |
| Settlement (FR13-FR22) | `use_cases/settlements.py`, `ports.py` | `settlement_adapter.py`, `queries/settlement_queries.py` | `web/settlements.py` | `settlements/` |
| Recurring Costs (FR23-FR29) | `use_cases/recurring.py`, `ports.py` | `recurring_adapter.py` | `web/recurring.py` | `recurring/` |
| Dashboard & Overview (FR30-FR38) | — (view concern) | `queries/dashboard_queries.py` | `web/dashboard.py` | `dashboard/` |
| User Management (FR39-FR42) | `models.py` | `queries/dashboard_queries.py` | `web/auth.py` | `auth/` |
| Audit & History (FR43-FR44) | `ports.py` (AuditPort) | `audit_adapter.py`, `queries/audit_queries.py` | `web/dashboard.py` | `dashboard/` |

**Cross-Cutting Concerns Mapping:**

| Concern | Location |
| --- | --- |
| Authentication (OIDC) | `app/auth/oidc.py`, `app/auth/session.py` |
| Session + CSRF middleware | `app/auth/middleware.py` |
| Global error handling | `app/main.py` (exception handlers + `DOMAIN_ERROR_MAP`) |
| Logging configuration | `app/logging.py` (structlog setup, called from `main.py`) |
| App configuration | `app/settings.py` (pydantic-settings `Settings` class) |
| Dependency wiring | `app/dependencies.py` |
| Health check | `app/main.py` (`/health` endpoint) |
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
- GHCR: `.github/workflows/docker.yml` (build + push)
- ArgoCD: watches GHCR for new images (external to repo)

**Data Flow (write path with UoW context manager):**

```text
Browser → HTMX POST → web/expenses.py
  → with uow: [
      use_cases/expenses.py → UnitOfWork
        → ExpensePort.save(actor_id=user_id) → SqlAlchemyExpenseAdapter
          → compute_changes() + AuditAdapter.log() → Session
    ] → UnitOfWork.__exit__() → Session.commit() → PostgreSQL
  → Jinja2 template (after context close) → HTML fragment
```

**Data Flow (read path — view query with UoW context manager):**

```text
Browser → HTMX GET → web/dashboard.py
  → with uow: [
      queries/dashboard_queries.py → Session.execute(SELECT ...) → PostgreSQL
        → DashboardData
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
      use_cases/settlements.confirm_settlement(uow, expense_ids, actor_id)
        → Validate expenses still available (SELECT FOR UPDATE)
        → uow.settlements.create(reference=generate_reference(), actor_id=actor_id)
        → uow.expenses.link_to_settlement(expense_ids, settlement_id, actor_id)
        → uow.commit()
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

**Transfer Direction Calculation:**

Location: `app/domain/splits.py` (pure function)

```python
def calculate_settlement_transfer(
    user1_balance: Decimal,  # Positive = owes money, Negative = owed money
    user2_balance: Decimal,
    user1_id: int,
    user2_id: int,
) -> TransferDirection:
    """
    Returns who pays whom based on net group balance.
    If user1 has positive balance (owes), user1 pays user2.
    """
    net = user1_balance + user2_balance  # Should be ~0 for 2-person
    if user1_balance > 0:
        return TransferDirection(from_user=user1_id, to_user=user2_id, amount=user1_balance)
    elif user2_balance > 0:
        return TransferDirection(from_user=user2_id, to_user=user1_id, amount=user2_balance)
    else:
        return TransferDirection(from_user=None, to_user=None, amount=Decimal("0"))  # No transfer
```

**Expense Selection Pattern:**

1. **Review page** displays all unsettled expenses for group
2. Each expense has checkbox with `name="expense_ids" value="{expense.id}"`
3. JavaScript-less form submission works (standard HTML checkboxes)
4. HTMX-enhanced: `hx-post="/settlements/confirm" hx-target="#content"`
5. Confirm page receives `expense_ids` list, validates, shows summary
6. Confirm form includes hidden inputs re-posting the same `expense_ids`
7. Final POST creates settlement atomically

**Key Implementation Notes:**

- **Concurrency protection**: `SELECT FOR UPDATE` on expenses during settlement creation
- **Idempotency**: Unique constraint on `(group_id, reference)` prevents duplicate monthly settlements
- **Validation**: Confirm page re-validates that all selected expenses are still unsettled (race condition protection)
- **Audit**: Settlement creation + expense linking both audited with `actor_id`

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
- `docs/deployment/` — ops/self-hosters (assumes Docker + k8s, not necessarily Python)
- `docs/architecture/` — contributors (condensed overview with Mermaid diagrams, links to full architecture.md)

**API documentation:** Swagger UI at `/docs` is the API reference (auto-generated by FastAPI). No separate `docs/api/`
section. Documentation is publicly viewable; API execution requires authentication.

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
