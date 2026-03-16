# Cost Tracker

Self-hosted household expense-sharing app for two partners. FastAPI + PostgreSQL + Jinja2 + HTMX + Tailwind CSS. Python 3.14, uv for package management.

## Architecture

Hexagonal (ports & adapters). Domain is pure Python — no framework imports.

```
app/
├── domain/          # @dataclass models, Protocol ports, use cases, pure math
├── adapters/        # SQLAlchemy implementations of domain ports
│   └── sqlalchemy/
│       ├── orm_models.py        # Declarative Base + XxxRow classes
│       ├── *_adapter.py         # SqlAlchemyXxxAdapter implementations
│       ├── unit_of_work.py      # Shared Session across adapters
│       └── queries/             # Read-only view queries (no writes)
├── auth/            # OIDC (Authentik + Authlib), signed cookie sessions, CSRF
├── web/             # Route handlers, Jinja2 templates, Pydantic forms
│   └── forms/       # Pydantic models for form validation (not domain models)
├── dependencies.py  # Composition root — only file that wires adapters to ports
├── main.py          # App factory, global exception handlers, middleware
├── settings.py      # pydantic-settings
└── logging.py       # structlog config
```

### Boundaries

- `domain/` imports only stdlib (`dataclasses`, `typing`, `decimal`, `datetime`, `enum`)
- ORM models (`XxxRow`) never leave adapter boundary — mapped to domain `@dataclass` via `_to_domain()` / `_to_row()`
- Use cases receive `UnitOfWork` as parameter — no global state, no service locator
- Current user enters domain as `user_id: int`, not framework request context
- `dependencies.py` is the only file that wires adapters to domain ports
- Routes call use cases for mutations, `queries/` directly for read-only views
- `queries/` is read-only — no writes permitted (enforced by architectural test)

## Naming Conventions

### Code
- Domain ports: `XxxPort` (e.g., `ExpensePort`)
- Adapters: `SqlAlchemyXxxAdapter` (e.g., `SqlAlchemyExpenseAdapter`)
- ORM models: `XxxRow` (e.g., `ExpenseRow`)
- Domain models: `@dataclass` with plain name (e.g., `Expense`)
- Test files: `{module}_test.py` (e.g., `expenses_test.py`)
- Templates: `snake_case.html`, HTMX partials prefixed `_` (e.g., `_row.html`)

### Database
- Tables: `snake_case`, **plural** (e.g., `expenses`, `recurring_definitions`)
- Foreign keys: `{referenced_table_singular}_id`
- Indexes: `ix_{table}_{columns}`
- Unique constraints: `uq_{table}_{columns}`

### API
- REST endpoints: **plural** nouns, `snake_case` paths
- HTMX endpoints share page paths, distinguished by `HX-Request` header
- API gets `/api/v1/` prefix (deferred post-MVP)

## Mandatory Rules

- Follow `XxxPort` / `SqlAlchemyXxxAdapter` / `XxxRow` naming — no variations
- Never add `try/except` for domain errors in route handlers — use the global exception handler (`DOMAIN_ERROR_MAP`)
- Never import framework packages in `domain/` — enforced by `architecture_test.py`
- Never use `utils.py` or `helpers.py` as file names — name by purpose (e.g., `splits.py`, `formatting.py`)
- Never write to DB in `queries/` — enforced by architectural test
- Always use `Decimal` for money values — zero floats in the money path
- Always call `uow.audit.log()` in use cases that perform state-changing operations
- Money in JSON: string representation of `Decimal` (e.g., `"123.45"`) — never float
- Dates in JSON: ISO 8601 strings
- No `Repository` naming — use `Port` (domain) + `Adapter` (infra)

## Error Handling

Single global exception handler in `main.py` maps `DomainError` subclasses to HTTP responses via `DOMAIN_ERROR_MAP`. Route handlers stay clean — validate input, call use case, render response. New domain errors only need an entry in the map.

## Testing

```
tests/
├── conftest.py              # SQLite in-memory engine, session/UoW factories
├── architecture_test.py     # Domain purity, queries read-only, no utils.py
├── domain/                  # Use cases via real adapters + SQLite
├── adapters/                # Adapter CRUD + contract_test.py (round-trip mapping)
├── integration/             # PostgreSQL (CI-only, TEST_DATABASE_URL)
└── web/                     # TestClient + template assertions
```

- pytest config requires `python_files = ["*_test.py"]` in `pyproject.toml`
- `architecture_test.py` enforces: domain import purity, `queries/` read-only, no `utils.py`/`helpers.py`
- `contract_test.py` validates round-trip ORM mapping preserves all fields

## Dev Workflow

- **Package manager:** `uv` (Astral) — never use pip directly
- `uv add <pkg>` — add dependency, `uv sync --locked` — install from lockfile
- `uv.lock` is committed for reproducible builds
- `mise run dev` — uvicorn with reload + tailwindcss --watch
- `mise run test` — pytest (unit tests, SQLite)
- `mise run lint` — ruff check + ruff format --check + ty
- `mise run migrate` — alembic upgrade head
- `mise run db` — docker-compose up -d (PostgreSQL)

## Deployment

Single Docker image (multi-stage: uv builder + Tailwind build → production). No Node.js at runtime.
Builder: `ghcr.io/astral-sh/uv:python3.14-bookworm-slim`. Production: `python:3.14-slim-bookworm`.
GHCR → ArgoCD → k3s. PostgreSQL on separate Proxmox VM.

## Sub-Agents

Use the project sub-agents (`.claude/agents/`) to delegate specialized work instead of doing everything in the main conversation.

**Knowledge oracles** — delegate questions to avoid loading full docs into context:
- `architecture-lead` — architecture decisions, patterns, boundaries, naming. Ask instead of reading `docs/architecture/` yourself
- `ux-lead` — UX decisions, component behavior, user flows, visual design. Ask instead of reading `docs/ux-design/` yourself

**Workflow agents** — delegate after implementation work:
- `pr-reviewer` — review code changes against architecture rules and CLAUDE.md before committing
- `tester` — run tests, check architecture enforcement, identify missing coverage
- `tech-writer` — create or update documentation in `docs/`

## Planning Artifacts

- PRD: `_bmad-output/planning-artifacts/prd.md`
- Architecture (sharded): `docs/architecture/`
- UX Design (sharded): `docs/ux-design/`
- Product Brief: `_bmad-output/planning-artifacts/product-brief-cost-tracker-2026-03-15.md`
