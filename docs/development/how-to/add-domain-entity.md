# Add a Domain Entity

Step-by-step guide for adding a new domain entity through all architectural layers. Uses the
project's hexagonal architecture pattern.

## Overview

A new entity touches these files, in order:

1. `app/domain/models.py` — `XxxBase` + `XxxPublic`
2. `app/domain/ports.py` — `XxxPort` Protocol
3. `app/domain/errors.py` — Domain errors (optional)
4. `app/adapters/sqlalchemy/orm_models.py` — `XxxRow`
5. `app/adapters/sqlalchemy/xxx_adapter.py` — `SqlAlchemyXxxAdapter`
6. `app/adapters/sqlalchemy/unit_of_work.py` — Wire adapter
7. `app/domain/use_cases/xxx.py` — Business operations
8. `app/web/xxx.py` — Route handlers
9. `alembic/versions/NNN_add_xxx.py` — Database migration

## Step 1: Domain Model

In `app/domain/models.py`, define the base and public models:

```python
class WidgetBase(SQLModel):
    """Domain base — validation + business data. No table."""

    name: str = Field(max_length=255)
    amount: Decimal = Field(decimal_places=2, ge=0.01)
    payer_id: int
    category: str | None = Field(default=None, max_length=50)
    is_active: bool = Field(default=True)


class WidgetPublic(WidgetBase):
    """Output schema — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime
```

Rules:

- `XxxBase` has business fields + validation only
- `XxxPublic` adds `id`, `created_at`, `updated_at`
- Use `Decimal` for money, `Field()` for constraints
- No `table=True` — these are not ORM models

## Step 2: Domain Port

In `app/domain/ports.py`, define the persistence interface:

```python
class WidgetPort(Protocol):
    def save(self, widget: WidgetPublic, *, actor_id: int) -> WidgetPublic: ...
    def get_by_id(self, widget_id: int) -> WidgetPublic | None: ...
    def list_all(self) -> list[WidgetPublic]: ...
    def update(self, widget_id: int, *, actor_id: int, name: str | None = None) -> WidgetPublic: ...
    def soft_delete(self, widget_id: int, *, actor_id: int) -> None: ...
```

Add it to `UnitOfWorkPort`:

```python
class UnitOfWorkPort(Protocol):
    users: UserPort
    expenses: ExpensePort
    # ...
    widgets: WidgetPort  # Add here
```

Rules:

- All mutating methods take `actor_id: int` as keyword-only
- Return `XxxPublic`, never `XxxRow`
- Use `| None` for optional returns

## Step 3: Domain Errors (optional)

In `app/domain/errors.py`:

```python
class WidgetNotFoundError(DomainError):
    """Raised when a widget cannot be found."""
    pass
```

Add to `DOMAIN_ERROR_MAP` in `app/main.py` to map to HTTP status:

```python
DOMAIN_ERROR_MAP = {
    # ...
    WidgetNotFoundError: 404,
}
```

## Step 4: ORM Model

In `app/adapters/sqlalchemy/orm_models.py`:

```python
class WidgetRow(WidgetBase, table=True):
    __tablename__ = "widgets"

    amount: Decimal = Field(sa_type=sa.Numeric(precision=19, scale=2))

    id: int | None = Field(default=None, primary_key=True)
    deleted_at: datetime | None = Field(default=None, sa_type=_TZ_DATETIME)
    created_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now()},
        sa_type=_TZ_DATETIME,
    )
    updated_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        sa_type=_TZ_DATETIME,
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"]),
        sa.Index("ix_widgets_payer_id", "payer_id"),
    )
```

Add to `__all__` at the bottom of the file.

Rules:

- Override base fields to specify `sa_type` for precise DB types
- Use `_TZ_DATETIME` for all datetime columns
- Use `server_default=func.now()` — never assign timestamps manually
- Add indexes and foreign keys in `__table_args__`

## Step 5: Adapter

Create `app/adapters/sqlalchemy/widget_adapter.py`:

```python
from app.adapters.sqlalchemy.audit_adapter import SqlAlchemyAuditAdapter
from app.adapters.sqlalchemy.changes import compute_changes, snapshot_new
from app.adapters.sqlalchemy.orm_models import WidgetRow
from app.domain.errors import WidgetNotFoundError
from app.domain.models import WidgetPublic


class SqlAlchemyWidgetAdapter:
    def __init__(self, session: Session, audit: SqlAlchemyAuditAdapter) -> None:
        self._session = session
        self._audit = audit

    def save(self, widget: WidgetPublic, *, actor_id: int) -> WidgetPublic:
        row = WidgetRow(payer_id=widget.payer_id, name=widget.name, amount=widget.amount)
        changes = snapshot_new(row, exclude={"id", "created_at", "updated_at", "deleted_at"})
        self._session.add(row)
        self._session.flush()
        self._audit.log(
            action="widget_created", actor_id=actor_id,
            entity_type="widget", entity_id=row.id, changes=changes,
        )
        return self._to_public(row)

    def get_by_id(self, widget_id: int) -> WidgetPublic | None:
        row = self._session.get(WidgetRow, widget_id)
        return self._to_public(row) if row else None

    def update(self, widget_id: int, *, actor_id: int, name: str | None = None) -> WidgetPublic:
        row = self._session.get(WidgetRow, widget_id)
        if row is None or row.deleted_at is not None:
            raise WidgetNotFoundError(f"Widget {widget_id} not found")
        if name is not None:
            row.name = name
        changes = compute_changes(row)
        self._session.add(row)
        self._session.flush()
        if changes:
            self._audit.log(
                action="widget_updated", actor_id=actor_id,
                entity_type="widget", entity_id=widget_id, changes=changes,
            )
        return self._to_public(row)

    def _to_public(self, row: WidgetRow) -> WidgetPublic:
        return WidgetPublic(
            id=row.id, payer_id=row.payer_id, name=row.name, amount=row.amount,
            category=row.category, is_active=row.is_active,
            created_at=row.created_at, updated_at=row.updated_at,
        )
```

Rules:

- Constructor takes `session` + `audit` adapter
- `save()` uses `snapshot_new()` then `flush()` then `audit.log()`
- `update()` uses `compute_changes()` before flush
- `_to_public()` converts `XxxRow` to `XxxPublic` — Row never leaves adapter

## Step 6: Wire to Unit of Work

In `app/adapters/sqlalchemy/unit_of_work.py`, add the adapter:

```python
from app.adapters.sqlalchemy.widget_adapter import SqlAlchemyWidgetAdapter

class UnitOfWork:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.audit = SqlAlchemyAuditAdapter(session)
        # ... existing adapters ...
        self.widgets = SqlAlchemyWidgetAdapter(session, self.audit)
```

## Step 7: Use Cases

Create `app/domain/use_cases/widgets.py`:

```python
from app.domain.errors import UserNotFoundError
from app.domain.models import WidgetPublic
from app.domain.ports import UnitOfWorkPort


def create_widget(
    uow: UnitOfWorkPort,
    payer_id: int,
    actor_id: int,
    name: str,
    amount: Decimal,
) -> WidgetPublic:
    payer = uow.users.get_by_id(payer_id)
    if payer is None:
        raise UserNotFoundError(f"User {payer_id} not found")

    widget = WidgetPublic.model_construct(
        id=0, payer_id=payer_id, name=name, amount=amount,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    return uow.widgets.save(widget, actor_id=actor_id)
```

Rules:

- Accept `uow: UnitOfWorkPort` — not the concrete `UnitOfWork`
- Validate preconditions (group exists, etc.) before calling adapter
- Raise domain errors, not `ValueError`
- The caller wraps in `with uow:` for transaction management

## Step 8: Route Handlers

See [Add a Route](add-route.md) for the full pattern. The key points:

- Get `UnitOfWork` via `Depends(get_uow)`
- Get user ID via `Depends(get_current_user_id)`
- Wrap use case calls in `with uow:`
- Domain errors are handled by the global exception handler

## Step 9: Database Migration

See [Add a Migration](add-migration.md) for the full process.

## Checklist

```text
Domain:
  [ ] XxxBase in app/domain/models.py
  [ ] XxxPublic in app/domain/models.py
  [ ] XxxPort Protocol in app/domain/ports.py
  [ ] Add to UnitOfWorkPort
  [ ] Domain errors in app/domain/errors.py
  [ ] Add errors to DOMAIN_ERROR_MAP in app/main.py

Adapter:
  [ ] XxxRow in app/adapters/sqlalchemy/orm_models.py (add to __all__)
  [ ] SqlAlchemyXxxAdapter in app/adapters/sqlalchemy/xxx_adapter.py
  [ ] Wire in app/adapters/sqlalchemy/unit_of_work.py

Use Cases:
  [ ] app/domain/use_cases/xxx.py

Routes:
  [ ] app/web/xxx.py
  [ ] Register router in app/web/router.py

Database:
  [ ] Alembic migration
  [ ] Run: mise run migrate

Tests:
  [ ] Contract test in tests/adapters/
  [ ] Use case test in tests/domain/
  [ ] Route test in tests/web/
```
