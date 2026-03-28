# Code Review: Production Readiness Assessment

**Date:** 2026-03-28
**Scope:** Full codebase review — domain, adapters, web, auth, migrations, tests, deployment
**Status:** Pre-deployment (no production data, migrations can be rewritten)

---

## Summary

The codebase is well-architected with clean hexagonal boundaries, comprehensive tests, and good patterns in many areas. However, there are **6 P1 issues** (bugs/security), **18 P2 issues** (maintainability/consistency), and **8 P3 issues** (nice-to-haves) that should be addressed before going live.

---

## P1 — Must Fix (Bugs, Data Integrity, Security)

### F-01: Python 2 exception syntax causes silent bugs

**Files:** `app/web/expenses.py:213,220,358,402,969,1019`, `app/web/recurring.py:685,733`, `alembic/env.py:44`

Six locations use Python 2 `except` syntax:

```python
except InvalidOperation, ValueError:  # WRONG — catches InvalidOperation, binds to name ValueError
```

In Python 3, `except X, Y:` catches `X` and binds the exception to variable `Y`. This means `ValueError` is silently rebound to the caught exception object, and actual `ValueError` exceptions are **not caught**. The correct syntax is:

```python
except (InvalidOperation, ValueError):  # CORRECT — catches both
```

**Impact:** Runtime bugs when `ValueError` is raised — it propagates instead of being caught. Also corrupts the `ValueError` name in scope.

**Fix:** Replace all 9 occurrences with tuple syntax.

---

### F-02: CSRF and webhook token comparison not timing-safe

**Files:** `app/auth/middleware.py:105,121`, `app/web/api_internal.py:31`

Token comparisons use `==` operator:

```python
# middleware.py:105
if header_token == expected_token:   # timing-safe vulnerability

# api_internal.py:31
if authorization != expected:        # timing-safe vulnerability
```

**Impact:** Timing side-channel attack could leak token bytes. Low practical risk for CSRF (tokens are per-session), but higher risk for the webhook secret (static, long-lived).

**Fix:** Use `hmac.compare_digest()` for all secret comparisons.

---

### F-03: `expense_row_to_public()` in mappings.py drops 3 fields

**File:** `app/adapters/sqlalchemy/queries/mappings.py:20-33`

The shared mapping function omits `recurring_definition_id`, `billing_period`, and `is_auto_generated` — fields that exist on `ExpensePublic`. Compare with `expense_adapter.py:_to_public()` which includes all fields.

**Impact:** View queries using this mapping silently return expenses with missing recurring metadata. Affects dashboard, filtering, and settlement review pages.

**Fix:** Add the three missing fields to `expense_row_to_public()`.

---

### F-04: `count_active_admins()` fetches all rows then calls `len()`

**File:** `app/adapters/sqlalchemy/user_adapter.py:214-220`

```python
def count_active_admins(self) -> int:
    statement = select(UserRow).where(...)
    result = self._session.exec(statement).all()  # fetches ALL admin rows
    return len(result)
```

**Impact:** Loads all admin user objects into memory just to count them. For a household app this is fine now, but it's wrong by principle — and the same pattern is used for security-critical checks (preventing last-admin deactivation).

**Fix:** Use `select(func.count()).where(...)` to count at the database level.

---

### F-05: `snapshot_new()` / `snapshot_deleted()` skip falsy values

**File:** `app/adapters/sqlalchemy/changes.py`

These functions filter `if value is not None` but will also skip legitimate values like `0`, `False`, `""`, empty list. For audit purposes this means:
- Setting `is_active = False` won't be captured in audit log
- Setting `tracking_threshold = 0` won't be captured

**Fix:** Use `if value is not None` explicitly (it already does this) but also include `False`, `0` — change filter to `if key not in exclude` and let the serializer handle None.

---

### F-06: Dockerfile runs as root

**File:** `Dockerfile:44-62`

The production stage has no `USER` directive — uvicorn runs as root inside the container.

**Fix:** Add a non-root user:

```dockerfile
RUN adduser --system --no-create-home appuser
USER appuser
```

---

## P2 — Should Fix (Maintainability, Simplification, Consistency)

### F-07: Squash 8 migrations into 1 for clean first deployment

**Files:** `alembic/versions/001_*.py` through `008_*.py`

Since there's no production data, the 8 incremental migrations add unnecessary complexity. Migration 001 creates tables missing columns that 002 adds, 005 adds expense_splits that should have been in 003, etc.

**Recommendation:** Squash into a single `001_initial_schema.py` that creates the complete schema. Benefits:
- Simpler `alembic upgrade head` for fresh deployments
- No intermediate states that could confuse future developers
- Eliminates inconsistencies (some migrations use `sa.DateTime(timezone=True)`, others use `postgresql.TIMESTAMP(timezone=True)`)

---

### F-08: PostgreSQL ENUM types will cause migration pain

**Files:** All migrations creating ENUMs

The schema uses native PostgreSQL ENUMs (`splittype`, `roletype`, `expensestatus`, `recurringfrequency`). Adding a new value (e.g., a new `SplitType`) requires:

```sql
ALTER TYPE splittype ADD VALUE 'NEW_VALUE';
-- Cannot be done inside a transaction in some PostgreSQL versions
```

**Impact:** Future schema changes are harder. The `MemberRole` and `UserRole` enums also share the same `roletype` DB enum, which is fragile — if one needs a new value the other doesn't.

**Recommendation:** Consider using `VARCHAR` with CHECK constraints instead of native ENUMs. This is a pre-deployment decision — much harder to change later.

---

### F-09: `MemberRole` and `UserRole` share `roletype` ENUM

**Files:** `app/domain/models.py:49-60`, `app/adapters/sqlalchemy/orm_models.py:43,58`

Both `MemberRole` (group-level) and `UserRole` (app-level) map to the same `roletype` PostgreSQL ENUM. They currently have identical values (ADMIN, USER) but serve different purposes.

**Risk:** If one needs a new role (e.g., group `VIEWER`), it affects the other.

**Fix:** Create separate ENUM types: `memberrole` and `userrole`.

---

### F-10: Port methods accept `*Public` models as input

**Files:** `app/domain/ports.py:146-152,199-209,238-240`

`ExpensePort.save()`, `SettlementPort.save()`, and `RecurringDefinitionPort.save()` all accept `*Public` models which include `id`, `created_at`, `updated_at` — DB-generated fields that shouldn't be caller-provided.

**Impact:** Callers must construct objects with dummy values (`id=0, created_at=None`) — see `use_cases/expenses.py` and `use_cases/recurring.py` with `# type: ignore` comments.

**Fix:** Accept `*Base` models (or create dedicated `*Create` DTOs) for save operations.

---

### F-11: `ExpensePort.update()` uses `Any` type for several parameters

**File:** `app/domain/ports.py:163-174`

```python
def update(self, expense_id: int, *, actor_id: int,
           amount: Any | None = None, date: Any | None = None,
           split_type: Any | None = None) -> None:
```

**Impact:** No compile-time type checking on update parameters.

**Fix:** Use proper types: `amount: Decimal | None`, `date: date | None`, `split_type: SplitType | None`.

---

### F-12: Recurring queries return template-ready dicts instead of domain models

**File:** `app/adapters/sqlalchemy/queries/recurring_queries.py`

`_build_definition_view()` returns raw dicts with pre-computed template flags (`is_auto_generate`, `is_manual_mode`, `frequency_label`, `initials`). This violates the hexagonal architecture — the query layer knows about presentation concerns.

**Fix:** Return `RecurringDefinitionPublic` from queries; compute template flags in a view model (like `admin.py` does with `UserRowViewModel`).

---

### F-13: Inconsistent audit logging patterns across adapters

**Files:** All adapter files

Three different patterns are used:
1. `snapshot_new()` / `compute_changes()` / `snapshot_deleted()` from `changes.py` (user, expense save/update)
2. Manual dict construction (expense splits, notes, settlement, soft-delete)
3. No change details at all (some edge cases)

**Fix:** Standardize on `changes.py` utilities for all audit logging. Add a `snapshot_partial_update()` helper if needed.

---

### F-14: N+1 query patterns in web handlers

**Files:** `app/web/settlements.py:41-51`, `app/web/recurring.py:108-117`, `app/web/expenses.py` (multiple)

Multiple handlers build user display name dicts by looping and calling `uow.users.get_by_id()` per user:

```python
def _get_user_display_names(uow, member_ids):
    return {uid: uow.users.get_by_id(uid).display_name for uid in member_ids}
```

**Fix:** Add a batch query: `get_users_by_ids(user_ids: list[int]) -> list[UserPublic]` to `UserPort` and `SqlAlchemyUserAdapter`.

---

### F-15: Inconsistent UoW context manager usage for reads

**Files:** `app/web/settlements.py` (6 endpoints), `app/web/expenses.py` (~10 endpoints), `app/web/admin.py` (2 endpoints)

Mutation endpoints correctly use `with uow:` but read-only endpoints often skip it. While technically the session lifecycle is managed by `get_db_session()`, the inconsistency is confusing.

**Recommendation:** Either always use `with uow:` for consistency, or document that read-only operations don't need it (and enforce via convention).

---

### F-16: Duplicated currency symbol mapping

**Files:** `app/web/expenses.py:82-90`, `app/web/settlements.py:30-38`, `app/web/filters.py:35-41`

The same `CURRENCY_SYMBOLS` dict exists in 3 files.

**Fix:** Define once in `app/web/filters.py` (already a Jinja2 filter) and import where needed.

---

### F-17: Manual form parsing alongside Pydantic validation

**Files:** `app/web/expenses.py:354-404`, `app/web/recurring.py:666-745`, `app/web/setup.py`

Handlers manually parse form fields (Decimal conversion, date parsing, JSON parsing) before or alongside Pydantic validation. This creates double-validation and inconsistent error handling.

**Fix:** Move all parsing into Pydantic form models with custom validators. Example: a `CreateExpenseForm` with `@field_validator` for amount, date, split_config.

---

### F-18: Business logic in route handlers instead of use cases

**Files:** `app/web/settlements.py:109-118,180-185`, `app/web/expenses.py` (split preview), `app/web/recurring.py:254-265`

Balance calculation, transaction minimization, and split validation happen in handlers:

```python
# settlements.py — should be in use case
balances = calculate_balances(expenses, member_ids, config)
transactions = minimize_transactions(balances)
```

**Fix:** Create a `preview_settlement()` use case or query function.

---

### F-19: Missing indexes on frequently-queried columns

**Files:** `alembic/versions/003_add_expenses.py`, ORM models

Missing indexes:
- `expenses.payer_id` — used in filter queries and balance calculation
- `expenses.creator_id` — used in queries
- `expenses.status` — used in WHERE clauses (PENDING, SETTLED, GIFT)
- `expenses.recurring_definition_id` — used for billing period lookups

These are currently unindexed FK columns that appear in common query patterns.

---

### F-20: Inconsistent timestamp column types across migrations

**Files:** Migrations 001-005 vs 006-008

Early migrations use `sa.DateTime(timezone=True)`, later ones use `postgresql.TIMESTAMP(timezone=True)`. They're equivalent in PostgreSQL but inconsistent in code.

**Fix:** Standardize on one style (prefer `sa.DateTime(timezone=True)` for portability).

---

### F-21: `settlement_expenses` join table missing CASCADE

**File:** `alembic/versions/004_add_settlements.py:40-47`

The `settlement_expenses` join table has plain FK constraints without `ondelete`. Deleting a settlement or expense won't cascade to this join table.

**Fix:** Add `ondelete="CASCADE"` to both foreign keys.

---

### F-22: Brittle IntegrityError parsing in expense adapter

**File:** `app/adapters/sqlalchemy/expense_adapter.py:48`

```python
if "uq_expenses_definition_billing_period" in str(exc.orig):
```

Parsing exception message strings is fragile and database-engine-dependent.

**Fix:** Use PostgreSQL's error code or constraint name from the exception object:

```python
if getattr(exc.orig, 'diag', None) and exc.orig.diag.constraint_name == "uq_expenses_definition_billing_period":
```

---

### F-23: `generate_reference_id()` has unbounded retry loop

**File:** `app/domain/use_cases/settlements.py:53-54`

```python
while uow.settlements.reference_exists(group_id, candidate):
    # keep incrementing suffix
```

No maximum iteration limit. If many settlements exist with the same month, this loops indefinitely.

**Fix:** Add a max retry limit (e.g., 100) and raise an error if exceeded.

---

### F-24: `alembic/env.py` has Python 2 except syntax

**File:** `alembic/env.py:44`

```python
except ValueError, TypeError:
```

Same issue as F-01 but in the migration tooling. Will cause migration generation to break if a `TypeError` is raised.

---

## P3 — Nice to Have

### F-25: Split strategies don't use `BalanceConfig` for rounding

**Files:** `app/domain/splits/strategies.py`, `app/domain/splits/config.py`

`BalanceConfig` exists with configurable rounding precision and mode, but all split strategies hardcode `ROUND_HALF_EVEN` and `Decimal("0.01")`.

**Recommendation:** Pass `BalanceConfig` to strategies for consistency.

---

### F-26: Money value object only used in balance.py

**File:** `app/domain/value_objects.py`

The well-designed `Money` value object is only used in `balance.py` and `splits/strategies.py`. Expenses, settlements, and adapters all use raw `Decimal` for amounts.

**Recommendation:** Consider wider adoption for type safety, or simplify to just functions if the class isn't pulling its weight.

---

### F-27: View models only used in admin module

**File:** `app/web/view_models.py`

`UserRowViewModel`, `UserProfileViewModel`, and `AuditEntryViewModel` are excellent patterns — but only admin endpoints use them. Expenses, settlements, and recurring handlers pass raw dicts to templates.

**Recommendation:** Create view models for all template data.

---

### F-28: Connection pool not configured

**File:** `app/dependencies.py:12`

```python
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
```

Uses default pool settings (pool_size=5, max_overflow=10). For a household app this is fine, but production should be explicit.

**Recommendation:** Add explicit pool configuration matching expected load.

---

### F-29: `ix_expenses_group_id` index is redundant

**File:** `alembic/versions/003_add_expenses.py:68`

`ix_expenses_group_id` is a single-column index on `group_id`, but `ix_expenses_group_id_date` is a composite index on `(group_id, date)`. PostgreSQL can use the composite index for `group_id`-only queries (leftmost prefix), making the single-column index redundant.

---

### F-30: Missing `__all__` exports in domain modules

**Files:** `app/domain/errors.py`, `app/domain/use_cases/*.py`

While not breaking, explicit `__all__` exports clarify the public API of each module.

---

### F-31: Skipped tests should be un-skipped or deleted

**Files:** `tests/web/dashboard_test.py`, `tests/auth/session_test.py`

Two tests are skipped with TODO comments. Before going live, these should either be fixed or removed with documentation of what they were testing.

---

### F-32: CI doesn't run architecture tests separately

**File:** `.github/workflows/code.yml`

Architecture tests run with all tests, but could be a separate fast job that catches violations early without needing PostgreSQL.

---

### F-33: Duplicate query in `save_splits` — result discarded

**File:** `app/adapters/sqlalchemy/expense_adapter.py:161`

```python
self._session.exec(select(ExpenseSplitRow).where(...))  # line 161 — result discarded
existing = self._session.exec(                           # line 162 — same query, kept
    select(ExpenseSplitRow).where(...)
).all()
```

The first `exec()` on line 161 runs the query and throws away the result. This is a bug — it should be removed.

---

### F-34: Redundant filter condition in `_filtered_expense_ids_subquery`

**File:** `app/adapters/sqlalchemy/queries/dashboard_queries.py:134-135`

```python
ExpenseRow.status == ExpenseStatus.PENDING,
ExpenseRow.status != ExpenseStatus.GIFT,    # redundant — already excluded by PENDING check
```

The second condition is dead code since `status == PENDING` already excludes GIFT.

---

### F-35: No deactivated-user check in AuthMiddleware

**File:** `app/auth/middleware.py`

`AuthMiddleware` validates the session cookie and extracts `user_id`, but never checks if the user is still active. A deactivated user with a valid (non-expired) session cookie can continue using the app until the cookie expires.

The deactivation check only happens during OIDC login callback (`provision_user`), not on subsequent requests.

**Fix:** Add an active-user check in middleware (with caching to avoid per-request DB lookups), or invalidate sessions on deactivation.

---

### F-36: Duplicate `_calculate_splits` function in web layer

**Files:** `app/domain/use_cases/expenses.py` (~line 132), `app/web/expenses.py` (~line 285)

The split calculation logic (strategy selection, share computation) exists in both the use case layer and the web handler layer (for split preview). These are structurally identical and should be consolidated.

**Fix:** Use the domain function from the web handler, or extract a shared helper in the domain layer.

---

### F-37: `expenses.py` is 1353 lines — too large for single module

**File:** `app/web/expenses.py`

Contains: expense list, creation (mobile + desktop forms), detail/edit, deletion, note CRUD, split preview, balance bar, feed filtering. This makes the file hard to navigate and review.

**Fix:** Split into sub-modules: `expense_crud.py`, `expense_partials.py`, `expense_notes.py`.

---

### F-38: Note CRUD methods missing from `ExpensePort` protocol

**Files:** `app/domain/ports.py`, `app/adapters/sqlalchemy/expense_adapter.py`

`SqlAlchemyExpenseAdapter` has methods `save_note`, `update_note`, `delete_note`, `list_notes_by_expense` that are NOT declared in `ExpensePort`. The web layer calls these through the concrete adapter type, bypassing the port abstraction.

**Fix:** Either add note methods to `ExpensePort`, or create a separate `ExpenseNotePort`.

---

## Priority Matrix

| Priority | Count | Action |
|----------|-------|--------|
| P1 | 8 | Must fix before deployment |
| P2 | 22 | Should fix for maintainability |
| P3 | 8 | Nice to have |

## Suggested Implementation Order

1. **F-01, F-24** — Fix Python 2 exception syntax (immediate, all files affected)
2. **F-02, F-35** — Add timing-safe comparisons + deactivated user check (security)
3. **F-03, F-33** — Fix incomplete mappings.py + duplicate query bug (data correctness)
4. **F-06** — Dockerfile non-root user (security)
5. **F-05** — Fix audit snapshot logic (data integrity)
6. **F-04, F-34** — Fix count query + redundant filter (correctness)
7. **F-07** — Squash migrations (clean slate opportunity)
8. **F-08, F-09** — Decide on ENUM strategy (architectural)
9. **F-19** — Add missing indexes (performance)
10. **F-10, F-11, F-38** — Fix port interface types + note methods (maintainability)
11. **F-36, F-37** — Consolidate duplicated code + split large file
12. Remaining P2 items grouped by affected area
13. P3 items as time permits
