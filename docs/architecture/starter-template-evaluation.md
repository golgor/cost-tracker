# Starter Template Evaluation

## Primary Technology Domain

Full-stack server-rendered web application (MPA + HTMX) with Python/FastAPI backend, based on project requirements
analysis.

## Starter Options Considered

**Existing starters evaluated:**

- **Full-Stack FastAPI Template** (tiangolo) — PostgreSQL, SQLModel, React frontend. Rejected: React frontend
  unnecessary, SQLModel not suitable for hexagonal architecture
- **FastAPI-HTMX starter** (various) — Minimal, mostly demo-quality. Rejected: too thin, no architectural opinions
- **Cookiecutter-FastAPI** — Configurable scaffolding. Rejected: generates flat service-layer structure, doesn't support
  ports & adapters

**Conclusion:** No existing starter matches the combination of FastAPI + HTMX + Jinja2 + ports & adapters. Custom
scaffolding is the correct approach.

## Selected Approach: Custom Scaffolding with Ports & Adapters

**Rationale:** The project requires a hexagonal architecture pattern that no existing FastAPI starter provides. Custom
scaffolding ensures clean domain boundaries from day one, avoiding costly restructuring later.

### Architectural Pattern: Ports & Adapters (Hexagonal Architecture)

Inspired by ArjanCodes' examples. The domain layer contains pure business logic with no framework imports.
Infrastructure concerns are pushed to adapters that implement domain-defined Protocol interfaces.

**Project Structure:**

```text
app/
  domain/                    # Pure business logic — NO framework imports
    models.py                # Domain dataclasses (@dataclass, not Pydantic)
    errors.py                # Domain exceptions
    ports.py                 # Protocol interfaces (ports)
    splits.py                # Split calculation (pure math helper, not a use case)
    use_cases/               # Business logic as plain functions (not classes)
      expenses.py
      settlements.py
      recurring.py
  adapters/
    sqlalchemy/              # DB adapters implementing domain ports
      orm_models.py          # SQLAlchemy mapped classes
      expense_adapter.py     # SqlAlchemyExpenseAdapter + _to_domain/_to_row
      settlement_adapter.py
      recurring_adapter.py
      audit_adapter.py
      unit_of_work.py        # UnitOfWork implementation (shared session)
  auth/                      # OIDC + session (infrastructure, not domain)
  web/                       # Page + HTMX routes (view-oriented fragments)
  api/v1/                    # JSON API routes (resource-oriented CRUD)
  dependencies.py            # Composition root — wires adapters to use cases
  templates/                 # Jinja2 templates
  static/                    # Vendored HTMX, Tailwind CSS output
tests/
  architecture_test.py       # Domain purity enforcement (AST-based)
```

**Domain Ports (Protocol Interfaces):**

```python
class ExpensePort(Protocol):
    def save(self, expense: Expense) -> Expense: ...
    def get_by_id(self, expense_id: int) -> Expense | None: ...
    def get_unsettled(self, group_id: int) -> list[Expense]: ...
    def get_for_settlement(self, expense_ids: list[int]) -> list[Expense]: ...
    def mark_settled(self, expense_ids: list[int], settlement_id: int) -> None: ...
    def delete(self, expense_id: int) -> None: ...

class SettlementPort(Protocol):
    def save(self, settlement: Settlement) -> Settlement: ...
    def get_by_id(self, settlement_id: int) -> Settlement | None: ...
    def get_history(self, group_id: int) -> list[Settlement]: ...

class RecurringPort(Protocol):
    def save_definition(self, definition: RecurringDefinition) -> RecurringDefinition: ...
    def get_pending_generation(self, as_of: date) -> list[RecurringDefinition]: ...
    def record_generation(self, definition_id: int, billing_period: str) -> None: ...

class AuditPort(Protocol):
    def log(self, entry: AuditEntry) -> None: ...

class UnitOfWork(Protocol):
    expenses: ExpensePort
    settlements: SettlementPort
    recurring: RecurringPort
    audit: AuditPort
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

**Key Architectural Decisions:**

1. **UnitOfWork pattern** — Domain port for transactional operations spanning multiple adapters. SQLAlchemy adapter
   shares a single session across all adapters within a UoW instance
2. **Audit as domain concern** — `AuditPort` is a domain port, called explicitly in use cases within the same UoW
   transaction. Atomic with data changes. Not a cross-cutting decorator
3. **Domain purity enforced** — `domain/` must not import from `fastapi`, `sqlalchemy`, `starlette`, or `pydantic`.
   Domain models are `@dataclass`. Enforced by `architecture_test.py` (AST-based, runs in CI)
4. **Port methods express intent** — Methods named for domain operations (`get_unsettled`, `mark_settled`) not generic
   CRUD (`find_by_status`)
5. **View queries bypass domain** — Read-only dashboard/search queries don't need domain ports. Only domain-significant
   operations get ports
6. **splits.py is a pure math helper** — Not a use case, doesn't need ports. Pure functions for split calculation
7. **ORM↔domain mapping co-located** — Mapping helpers live in each adapter file, not in a separate mapping module
8. **Dashboard composition is a view concern** — Web layer assembles data from multiple use cases; no "dashboard use
   case"
9. **Use cases are plain functions** — Receive `UnitOfWork` as parameter. No single-method classes
10. **Composition root** — `app/dependencies.py` wires SQLAlchemy adapters to use cases via FastAPI dependency
    injection. Current user enters domain as `user_id` parameter, not request context

**Testing Strategy:**

- **All tests** (`@pytest.mark.unit` and `@pytest.mark.integration`, SQLAlchemy + PostgreSQL with `_test` suffix):
  Domain logic through real adapters, split calculations, validation, state transitions
- **Integration tests** (`@pytest.mark.integration`, SQLAlchemy + PostgreSQL with `_test` suffix): Settlement
  concurrency (`SELECT FOR UPDATE`), unique constraint idempotency, transactional rollback behavior
- **End-to-end**: Full request cycle through routes → use cases → adapters → DB
- **Architectural test** (`architecture_test.py`): Walks `domain/` AST, asserts no forbidden framework imports

**Architectural Guardrails (from Pre-mortem Analysis):**

| # | Risk | Prevention | Check When |
| --- | ------ | ----------- | ------------ |
| 1 | Mapping tax kills velocity | Keep mappings minimal, co-located in adapter repo files | Every new field/model |
| 2 | Protocol explosion | Only domain-significant ops get ports; view queries bypass domain | Every new repo method |
| 3 | Test/Production DB divergence | All tests use PostgreSQL with `_test` suffix (auto-created) | Every test run |
| 4 | Framework leaking into domain | AST-based `architecture_test.py` in CI | Every PR |
| 5 | UoW scope creep | UoW = repos + commit + rollback, nothing more | Every UoW change |

**Initialization Command:**

```bash
mkdir -p app/{domain/use_cases,adapters/sqlalchemy,auth,web,api/v1,templates,static} tests
```

**Dependency Management:**

- `uv` is the package manager for this project (Python 3.14 target)
- Use `uv add <package>` to add dependencies, `uv sync --locked` to install, `uv.lock` is committed
- Docker builds use `ghcr.io/astral-sh/uv:python3.14-bookworm-slim` base image with `uv sync --locked` for reproducible
  deploys

**Note:** Project initialization and scaffolding should be the first implementation story.
