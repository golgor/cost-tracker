# Core Architectural Decisions

## Decision Priority Analysis

**Critical Decisions (Block Implementation):**

- ORM mapping style: Declarative with domain/ORM separation via adapter pattern
- Session-based transactions mapped to UnitOfWork port
- Port/adapter naming: `XxxPort` (domain), `SqlAlchemyXxxAdapter` (infrastructure), `XxxRow` (ORM internal)
- Authorization: business rules in use cases, user context via signed cookie
- Sync SQLAlchemy for MVP

**Important Decisions (Shape Architecture):**

- `uv` for fast, reproducible Python dependency management (`uv.lock` committed)
- Alembic for database migrations (auto-generated from declarative models, always manually reviewed)
- `pydantic-settings` for environment configuration
- `structlog` for logging (JSON in production, console in dev, switchable by `LOG_FORMAT` env var)
- FastAPI exception handlers for domain error to HTTP response mapping
- Swagger UI enabled behind OIDC authentication
- Jinja2 templates nested by domain area, `_` prefix for HTMX partials
- `mise` for local dev task running and tool version management
- Structured logging in all environments
- CI workflows split by path filters
- View queries in `adapters/sqlalchemy/queries.py` (read-only, enforced by architectural test)

**Deferred Decisions (Post-MVP):**

- API key authentication (evaluate Authentik client_credentials flow)
- API route layer (`/api/v1/`) — architecture supports adding later without domain changes
- Rate limiting
- Caching strategy
- CORS (not needed — same-origin browser + non-browser API clients)

## Data Architecture

| Decision | Choice | Rationale |
| --- | --- | --- |
| Database | PostgreSQL (external Proxmox VM) | Already decided in PRD |
| ORM | SQLModel (SQLAlchemy + Pydantic) | Domain models as `SQLModel` base classes; `XxxRow` inherits with `table=True` |
| Transaction management | SQLAlchemy `Session` via `UnitOfWork` port | Tracks changes, commits atomically. Maps naturally to domain UoW |
| Migrations | Alembic (auto-generate + manual review) | Standard for SQLAlchemy. Never blind upgrade — always review generated migrations |
| Configuration | `pydantic-settings` | Reads env vars, validates types, fails fast. `.env` for local dev (gitignored), `.env.example` committed |
| Caching | Deferred | Not needed for MVP |
| Timestamps | `TIMESTAMPTZ` + server-managed defaults (`server_default=func.now()`, `onupdate=func.now()`) | Timezone-aware storage, no Python-side clock dependency, automatic `updated_at` on every UPDATE |

**Adapter Pattern (not Repository Pattern):**

- Ports define what the domain needs: `ExpensePort(Protocol)`
- Adapters implement ports using infrastructure: `SqlAlchemyExpenseAdapter`
- ORM `XxxRow` inherits from domain `XxxBase` (SQLModel inheritance)
- Adapters use `_to_public()` to convert ORM rows to public domain models (e.g., `UserPublic`, `ExpensePublic`)
- No `_to_row()` helper needed — rows are created directly as `XxxRow(...)` since they inherit domain fields

**View Queries (`adapters/sqlalchemy/queries.py`):**

- Read-only queries for dashboard, search, and summary views
- Can use joins and aggregations for optimized reads
- Must not contain `session.add()`, `session.delete()`, or `session.commit()`
- Enforced by architectural test

Example — view query vs. port usage:

```python
# adapters/sqlalchemy/queries.py — view query (read-only, optimized for display)
def get_dashboard_summary(session: Session) -> DashboardData:
    """Joins expenses + users for dashboard display. Not domain logic."""
    rows = session.execute(
        select(ExpenseRow, UserRow.display_name)
        .join(UserRow, ExpenseRow.payer_id == UserRow.id)
        .where(ExpenseRow.settlement_id.is_(None))
    ).all()
    return DashboardData(...)

# domain/ports.py — port method (domain-significant operation)
class ExpensePort(Protocol):
    def get_for_settlement(self, expense_ids: list[int]) -> list[Expense]:
        """Used by settlement use case. Domain operation, not a view."""
        ...
```

## Authentication & Security

| Decision | Choice | Rationale |
| --- | --- | --- |
| Browser auth | OIDC via Authentik + Authlib, signed cookie (user_id + issued_at) | No tokens stored |
| API auth | Deferred post-MVP (evaluate Authentik client_credentials) | Browser-first MVP |
| Authorization | Business rules checked in use cases; user context from signed cookie | Domain logic in domain layer |
| CSRF | Browser mutations only (HTMX + form POST) | API uses separate auth path |
| CORS | Disabled (default deny) | Same-origin browser, non-browser API clients |

## API & Communication Patterns

| Decision | Choice | Rationale |
| --- | --- | --- |
| API style | REST at `/api/v1/` (deferred post-MVP) | Use cases ready, route layer added later |
| HTMX style | View-oriented fragments at shared page paths | Optimized for UI |
| API docs | Swagger UI at `/docs`, publicly viewable. API execution requires OIDC auth | Open-source project, no secrets in endpoint definitions |
| Error handling | FastAPI exception handlers mapping domain errors to HTTP | Per-layer response format (JSON for API, HTML fragment for HTMX) |
| Rate limiting | Deferred | Not needed at MVP scale |
| Versioning | `/api/v1/` prefix by convention | No versioning infrastructure needed |

## Frontend Architecture

| Decision | Choice | Rationale |
| --- | --- | --- |
| Rendering | Jinja2 server-side + HTMX partial swaps | No JavaScript framework, no Node.js |
| Template organization | Nested by domain area, `_` prefix for partials | Visual clarity, grouped by feature |
| Styling | Tailwind CSS, CLI build at Docker build time | No Node.js runtime dependency |
| HTMX versioning | Vendored in `static/`, version comment in file | Manual updates, self-contained |
| Dev tooling | `mise` (tasks + tool version management) | Runs tailwind watch + uvicorn reload |
| HTMX error handling | Single `_error.html` partial + global `hx-on::response-error` in `base.html` | Consistent error display across all HTMX requests |

## Infrastructure & Deployment

| Decision | Choice | Rationale |
| --- | --- | --- |
| Package manager | `uv` (Astral) | Fast, reproducible builds. `uv.lock` committed for deterministic deploys |
| Python version | Python 3.14 | Latest stable. Docker builder image: `ghcr.io/astral-sh/uv:python3.14-bookworm-slim` |
| Container | Single Docker image to GHCR | Multi-stage build: Tailwind CSS + app + dependencies. `uv sync --locked` for reproducibility |
| Orchestration | ArgoCD to k3s | Already decided |
| Database hosting | External PostgreSQL (Proxmox VM) | Separate from k3s cluster |
| Logging | `structlog` — JSON in production, console in dev (`LOG_FORMAT` env var) | Same structured data, format switchable |
| CI/CD | GitHub Actions, split by path filters | Code (pytest/ruff/ty), Docs (markdownlint), Docker (build/push) |
| Health check | `/health` endpoint | K8s liveness/readiness probe |
| Sync/Async | Sync SQLAlchemy for MVP | Simpler, sufficient for scale. Async is localized future change (adapter layer only) |

## Layer Import Rules

| Layer | Allowed Imports |
| --- | --- |
| `domain/` | stdlib + external validation libs (sqlmodel, pydantic, typing, decimal, datetime, enum). NO internal app imports. |
| `adapters/` | domain + sqlmodel + structlog |
| `auth/` | fastapi + authlib + pydantic |
| `web/` | fastapi + jinja2 + domain (models/errors for type hints) |
| `api/v1/` | fastapi + pydantic + domain (models/errors) |
| `dependencies.py` | everything (composition root) |

Domain layer does not log. It raises errors or uses `AuditPort`. Infrastructure logging (request timing, DB query stats)
happens in middleware and adapters only. Domain models use SQLModel for validation; ORM models inherit from domain
models with `table=True`.

## Testing Strategy (Updated)

- **All tests** (`@pytest.mark.unit` and `@pytest.mark.integration`, SQLAlchemy + PostgreSQL with `_test` suffix):
  Domain logic through real adapters, split calculations, validation, state transitions, concurrency tests
- **Integration tests** (`@pytest.mark.integration`, SQLAlchemy + PostgreSQL with `_test` suffix): Settlement
  concurrency (`SELECT FOR UPDATE`), unique constraint idempotency, transactional rollback, health checks
- **Contract tests** (`@pytest.mark.contract`, no DB needed): Verify ORM models inherit all domain base fields correctly
- **Architectural tests** (`architecture_test.py`): Domain import purity (AST-based), `queries.py` read-only enforcement
- **CI schema drift check**: After `alembic upgrade head`, verify schema matches `Base.metadata.create_all()` output
- **End-to-end**: Full request cycle through routes to use cases to adapters to DB

## Architectural Guardrails (Consolidated)

| # | Risk | Prevention | Check When |
| --- | ------ | ----------- | ------------ |
| 1 | ~~Mapping tax kills velocity~~ | Eliminated by SQLModel inheritance pattern (ADR-011) | N/A |
| 2 | Protocol explosion | Only domain-significant ops get ports; view queries bypass domain | Every new port method |
| 3 | Test/Production DB divergence | All tests use PostgreSQL with `_test` suffix (auto-created) | Every test run |
| 4 | Framework leaking into domain | AST-based `architecture_test.py` in CI | Every PR |
| 5 | UoW scope creep | UoW = repos + commit + rollback, nothing more | Every UoW change |
| 6 | `.env` secrets leak | `.gitignore`, `.env.example`, log config source on startup | Project setup |
| 7 | Migration/ORM schema drift | CI: compare Alembic output to `create_all()` | Every migration |
| 8 | `queries.py` write creep | Architectural test for read-only enforcement | Every `queries.py` change |
| 9 | Inconsistent HTMX errors | Single global handler + `_error.html` partial | Every HTMX endpoint |
| 10 | `dependencies.py` god file | Split by feature if >100 lines | When file grows |
| 11 | ~~Mapping field drift~~ | Eliminated by SQLModel inheritance — ORM inherits from domain | N/A |
| 12 | Manual timestamp drift | Server-managed defaults (`server_default`, `onupdate`) — no Python `datetime.now()` in adapters | Every new datetime column |

## Decision Impact Analysis

**Implementation Sequence** (aligned with PRD Phase 1 MVP):

1. Project scaffolding (directory structure, `mise` config, `pyproject.toml`)
2. CI pipeline skeleton (GitHub Actions: ruff + pytest on empty test suite)
3. Domain layer (models, errors, ports, splits)
4. SQLAlchemy adapters (ORM models, adapters, UnitOfWork, Alembic setup)
5. Auth infrastructure (OIDC, session middleware, CSRF)
6. Web route layer (HTMX pages + partials, dependency wiring)
7. Templates and static assets (Jinja2, HTMX, Tailwind)

Note: Implementation stories should reference PRD Phase 1 scope and feature boundaries, not just architecture layers.

**Cross-Component Dependencies:**

- Adapters depend on domain ports (by design)
- Routes depend on `dependencies.py` for adapter wiring
- Alembic depends on ORM models in `adapters/sqlalchemy/orm_models.py`
- CI workflows depend on project structure being established
- Contract tests depend on both domain models and ORM models existing

## Architecture Decision Records

### ADR-001: Ports & Adapters (Hexagonal Architecture)

**Status:** Accepted (Amended 2026-03-16)
**Context:** Need clean separation between business logic and infrastructure for long-term scalability.
**Decision:** Domain layer uses `Protocol` interfaces (ports). Adapters implement ports using SQLModel/SQLAlchemy.
Domain may import external validation libraries (SQLModel, Pydantic) but must not import internal application modules
(adapters, web, auth, api).
**Consequences:** Cleaner testability. Use cases reusable across route layers. Framework changes localized to adapters.
External validation libs in domain enable SQLModel pattern (see ADR-011).

### ADR-002: Declarative ORM with Adapter Separation

**Status:** Superseded by ADR-011 (2026-03-16)
**Context:** Need ORM for migration support. Imperative mapping has sparse documentation.
**Decision:** ~~Declarative `XxxRow(Base)` models internal to adapters. Domain models are `@dataclass`. Each adapter
contains `_to_domain()` / `_to_row()` helpers.~~
**Consequences:** ~~Two models per entity + mapping functions.~~ See ADR-011 for current approach.

### ADR-003: UnitOfWork as Domain Port

**Status:** Accepted
**Context:** Settlement flow requires atomic operations across expenses + settlements + audit.
**Decision:** `UnitOfWork(Protocol)` exposes all ports + `commit()`/`rollback()`. SQLAlchemy adapter shares single
`Session`. UnitOfWork implements context manager protocol (`__enter__`/`__exit__`) for automatic transaction management.

**Context Manager Usage:**

- All UoW operations (reads and writes via adapters) must occur inside `with uow:` block
- Automatic `commit()` on successful exit (no exception raised)
- Automatic `rollback()` on exception exit
- Template rendering must occur **after** the context manager closes to ensure session cleanup
- Do NOT nest `with uow:` blocks — enforced by implementation (raises error on re-entry)

**Route Handler Pattern:**

```python
@router.get("/path")
async def handler(
    request: Request,
    user_id: CurrentUserId,
    uow: UowDep,
):
    with uow:
        # All UoW operations inside context manager
        data = uow.adapter.get_something()
        # Session flushes/commits automatically on exit
    
    # Template rendering AFTER context manager closes
    return templates.TemplateResponse(...)
```

**Consequences:** Broad access accepted — discipline via code review. Simplifies dependency injection. Automatic
transaction management reduces boilerplate and prevents session leaks. Context manager boundary ensures templates
don't access closed sessions.

### ADR-004: Audit Logging as Domain Concern

**Status:** Accepted (Updated)
**Context:** Audit trail is a business requirement (FR43-44), not infrastructure. Original pattern required every use
case to call `uow.audit.log()` explicitly, which was repetitive and easy to forget.
**Decision:** Adapter-driven auto-auditing. Mutating adapter methods (`save()`, `update()`, `add_member()`) accept an
`actor_id` keyword parameter and create audit rows automatically using SQLAlchemy `inspect()` dirty tracking.
`compute_changes(row)` reads attribute history for updates (old→new for changed fields only). `snapshot_new(row)` builds
a changes dict for creates (old is always null). Changes stored as `{"field": {"old": ..., "new": ...}}` JSON. No audit
row is created if nothing actually changed. Audit rows share the same transaction as business data (atomicity via UoW).
User adapter's `save()` auto-audits with `actor_id` set to the user's own ID (self-provisioning via OIDC). `AuditPort`
still exists for direct use if needed, but adapters handle the common case.
**Consequences:** Audit logging cannot be accidentally omitted from mutations. Use case code is cleaner — no explicit
audit calls needed. Adapters receive the audit adapter via constructor injection. Slight coupling between adapters and
audit concern, accepted as pragmatic trade-off.

### ADR-005: Sync SQLAlchemy for MVP

**Status:** Accepted
**Context:** FastAPI supports async but sync is simpler for ~2-5 concurrent users.
**Decision:** Sync everywhere for MVP. Async migration is localized to adapter layer if needed later.
**Consequences:** Simpler code, easier debugging. Ports don't change if async is adopted later.

### ADR-006: View Queries Bypass Domain Ports

**Status:** Accepted
**Context:** Dashboard queries need joins/aggregations. Creating ports for every read would cause protocol explosion.
**Decision:** `adapters/sqlalchemy/queries.py` for read-only view queries. Routes import directly. Writes always go
through domain ports.
**Consequences:** Controlled bypass of hexagonal boundary. Enforced read-only by architectural test.

### ADR-007: API Routes Deferred Past MVP

**Status:** Accepted (Amended 2026-03-25)
**Context:** MVP is browser-first. Ports & adapters makes adding API consumers trivial.
**Decision:** HTMX/page routes for MVP. `/api/v1/` added as separate phase (target: Week 3-4 for external
dashboard integration).
**Consequences:** Faster MVP delivery. No domain changes needed when API is added. External dashboard (Glance)
satisfies dashboard requirements; cost-tracker focuses on expense management UI.

### ADR-008: Structured Logging with structlog

**Status:** Accepted
**Context:** Need machine-parseable logs in production and readable logs in dev.
**Decision:** `structlog` with `LOG_FORMAT` env var (json/console). Domain doesn't log — raises errors or uses
AuditPort.
**Consequences:** One library, two output modes. Infrastructure logging in middleware/adapters only.

### ADR-009: Split CI Workflows by Path

**Status:** Accepted
**Context:** Running all checks on every push wastes time.
**Decision:** Three workflows with `paths:` filters: Code, Docs, Docker. Schema drift check in Code workflow.
**Consequences:** Faster CI feedback. Path filters must cover all relevant files.

### ADR-010: pydantic-settings for Configuration

**Status:** Accepted
**Context:** App runs on k3s with env vars from Secrets/ConfigMaps.
**Decision:** Single `Settings` class via `pydantic-settings`. `.env` for local dev (gitignored). `.env.example`
committed.
**Consequences:** Simple, standard. Fails fast on missing config.

### ADR-011: SQLModel for Domain and ORM Models

**Status:** Accepted (2026-03-16)
**Context:** ADR-002 required separate domain dataclasses and ORM Row models with manual mapping. SQLModel unifies these
while maintaining separation via `table=True` flag.
**Decision:**

- Domain models: `SQLModel` classes without `table=True` (pure data + validation)
- ORM models: `SQLModel` classes with `table=True`, inheriting from domain models
- Mapping: Adapters use `_to_public()` to convert ORM rows to public domain models; rows created
  directly as `XxxRow(...)` — no `_to_row()` needed
**Consequences:**
- Single field definition per entity (in domain base class)
- ORM models inherit and add DB-specific fields (id, timestamps, foreign keys)
- Reduced code duplication. Contract tests simplified (inheritance ensures field consistency)
- Domain now depends on SQLModel (external library) — acceptable per amended ADR-001

### ADR-012: Human-Readable Settlement References

**Status:** Accepted
**Context:** Settlements need human-readable references for partner communication. "March 2025"
is more useful than "settle_abc123".
**Decision:**

- Settlement reference format: `{Month} {Year}` (e.g., "March 2025")
- Uniqueness scope: global (one settlement per month, app-wide)
- Auto-generated from settlement date, not user-editable
- Stored as `reference: str` in `SettlementRow`

**Consequences:**

- Simple, readable references for 2-person settlement flow
- Constraint: `UNIQUE(reference)` enforces one settlement per month
- Month names use full English names (January-December), capitalized
- Displayed in settlement history, detail views, and audit logs

### ADR-013: Soft Immutability for Settled Expenses

**Status:** Accepted
**Context:** Once expenses are included in a settlement, they should not be modified. Hard DB
constraints prevent admin override for corrections.
**Decision:**

- No database-level constraints preventing edits to settled expenses
- Immutability enforced at application layer (use cases + UI)
- Check `expense.settlement_id` before allowing edits/deletes
- Raise `ExpenseAlreadySettledError` if modification attempted

**Implementation:**

```python
# use_cases/expenses.py
def update_expense(
    uow: UnitOfWork, expense_id: int, actor_id: int, ...
):
    expense = uow.expenses.get_by_id(expense_id)
    if expense.settlement_id is not None:
        raise ExpenseAlreadySettledError(expense_id)
    # ... proceed with update
```

**Consequences:**

- Simpler schema (no complex constraint)
- Admin can override if necessary (direct DB access for corrections)
- UI shows "Settled" badge, disables edit buttons for settled expenses
- Audit trail maintains history if changes are made

### ADR-014: Stateless Settlement Review Flow

**Status:** Accepted
**Context:** Settlement review involves selecting which expenses to include, reviewing totals,
then confirming. Draft persistence adds complexity unnecessary for a 2-person app.
**Decision:**

- No draft settlement records stored in database
- Review state held entirely in form state (checkboxes for expense selection)
- Two-step flow: (1) Review page with selectable expenses, (2) Confirm page with summary
- POST on confirm creates settlement atomically via UoW

**Flow:**

```text
GET /settlements/review
  → Show all unsettled expenses with checkboxes
  → "Select All" / individual selection
  → Form POSTs selected expense_ids to /settlements/confirm

GET /settlements/confirm?expense_ids=1,2,3
  → Calculate totals, transfer direction, net amount
  → Display summary: "Alice owes Bob $123.45"
  → Form POSTs to /settlements (create)

POST /settlements
  → Use case validates expenses still unsettled
  → Creates settlement, links expenses, creates audit log
  → Redirect to settlement detail
```

**Consequences:**

- Simpler implementation (no draft state machine)
- No orphaned draft records
- Selection lost on browser refresh (acceptable trade-off)
- Suitable for 2-person use case where both partners settle together

### ADR-015: Landing Page Simplification

**Status:** Accepted (2026-03-25)
**Context:** External dashboard (Glance) handles overview needs. Internal dashboard route (`/`) duplicates expense
list functionality at `/expenses`. HTMX target conflicts between pages cause navigation errors.
**Decision:** Remove dashboard expense list. Route `/` permanently redirects (307) to `/expenses`. Navigation
removes "Dashboard" link; "Expenses" becomes primary navigation item.
**Consequences:**

- Single canonical path for expense management (`/expenses`)
- Eliminates HTMX target ID conflicts (`#expense-feed` is now the only target)
- Reduced template surface area (removed `dashboard/index.html`)
- Simpler mental model: cost-tracker is the expense management interface
- External dashboard (Glance) provides overview via planned API integration (Week 3-4)
